// native_adapter.c - 供 c_function_demo 调用的项目内 C 函数

// 把两个参数相加后再额外加 5，方便确认结果确实来自 C 层。
int neko_add_bonus(int base, int bonus) {
    return base + bonus + 5;
}

// 返回一个固定常量，演示无参数 extern 调用。
int neko_magic_number(void) {
    return 17;
}
