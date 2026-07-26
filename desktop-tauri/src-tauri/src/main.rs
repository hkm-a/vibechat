// 发布版本在 Windows 上不得额外打开控制台窗口，请勿删除。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    vibechat_lib::run();
}
