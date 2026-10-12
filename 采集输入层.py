#!/usr/bin/env python3
"""采集输入层.py — 两个采集脚本共用的**禁用输入法**层 (唯一来源; 2026-10-01)

问题: 输入法处于**中文态**时, 字母先被 IME 拿去组字 ⇒ tkinter 只收到 `keysym='??'` / `char=''`
      的 <KeyPress>, 采集脚本 (读 `event.char`) 判定"没有按键"; 而且 IME 会输出汉字、弹候选框。
      (同源项目的复现与三层修法见 `../并击击键当量/README.md` §4.1 与
       `../并击击键当量/实验/实验-IME按键捕获.py` —— 真实注入按键的实测。)

本模块 = **窗口级摘除** `ImmAssociateContext(hwnd, NULL)` —— 摘掉**本窗口**的输入上下文
  (SDL / Chromium / Wine 的通用做法):
  `ImeGuard(root)`: 建窗后调一次; 窗口每次激活 (<FocusIn>) 与每 2 s 重摘一次。
  为什么要重摘: 系统会在激活/切换输入法后重新关联, tkinter 自带 IME 支持也会在建窗/获焦时
  自己挂上下文 ⇒ 一次摘除不够, 必须周期性补摘。

**2026-10-12 用户决策「禁用 IME 的方法只保留摘除窗口 IME」**: 去掉原先并用的进程级
  `ImmDisableIME(0)` (须在第一个顶层窗口收到 WM_CREATE 之前调用, MSDN 硬约束) ⇒ 本模块只剩
  这一个入口, 也不再有任何"必须在建窗之前调用"的时序约束。

用法 (采集脚本里各 2 行):
    from 采集输入层 import ImeGuard
    ...  self.root = tk.Tk()  ...
    self.ime_guard = ImeGuard(self.root)     # 建窗后; 退出时 .stop()

不做的事: 本模块**不装低层键盘钩子** (并击项目那层是为"IME 连键都看不到"的额外保证);
  窗口级摘除已足够让中文态下的字母以干净 `char` 到达 tkinter ⇒ 串击保持脚本简单、无全局钩子。
"""
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _imm32 = ctypes.WinDLL("imm32", use_last_error=True)

    _GA_ROOT = 2
    _user32.GetAncestor.restype = ctypes.c_void_p
    _user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    _user32.GetFocus.restype = ctypes.c_void_p          # 默认 c_int 会截断 64 位句柄
    _imm32.ImmAssociateContext.restype = ctypes.c_void_p
    _imm32.ImmAssociateContext.argtypes = [wintypes.HWND, ctypes.c_void_p]

    def tk_toplevel(root):
        """tkinter 顶层窗口句柄 (winfo_id() 在 Windows 上返回内部子窗口; 顶层要 GA_ROOT)"""
        return _user32.GetAncestor(wintypes.HWND(root.winfo_id()), _GA_ROOT) or root.winfo_id()

    def ime_detach(root):
        """摘掉本窗口 (顶层 + 子窗口 + 本线程焦点窗口) 的输入上下文; 返回摘掉旧上下文的窗口数"""
        n = 0
        for h in {tk_toplevel(root), root.winfo_id(), _user32.GetFocus()}:
            if h and _imm32.ImmAssociateContext(wintypes.HWND(h), None):
                n += 1
        return n

    class ImeGuard:
        """窗口级 IME 摘除: 建窗后调一次; 激活时与每 interval_ms 重摘一次"""

        def __init__(self, root, interval_ms=2000):
            self.root, self.interval_ms = root, interval_ms
            self.n_detached = ime_detach(root)
            self._alive = True
            root.bind("<FocusIn>", self._on_focus, add="+")   # add="+" 不动脚本原有绑定
            self._tick()

        def _on_focus(self, event=None):
            if self._alive:
                ime_detach(self.root)

        def _tick(self):
            if not self._alive:
                return
            ime_detach(self.root)
            self.root.after(self.interval_ms, self._tick)

        def stop(self):
            self._alive = False

    def status():
        """给采集脚本打印的一行状态"""
        return "输入法: 窗口级摘除已启用 (ImmAssociateContext(hwnd, NULL))"

else:                                   # 非 Windows: 空实现 (IME 是 Windows 特性)
    def tk_toplevel(root):
        return 0

    def ime_detach(root):
        return 0

    class ImeGuard:
        def __init__(self, root, interval_ms=2000):
            self.n_detached = 0
            self._alive = True

        def stop(self):
            self._alive = False

    def status():
        return "输入法: 非 Windows 平台, 无需处理"


if __name__ == "__main__":
    print(f"IS_WINDOWS = {IS_WINDOWS}")
    if IS_WINDOWS:
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        g = ImeGuard(r)
        print("ImeGuard: 摘除窗口数 =", g.n_detached, "| tk_toplevel =", hex(tk_toplevel(r) or 0))
        g.stop(); r.destroy()
    print(status())
