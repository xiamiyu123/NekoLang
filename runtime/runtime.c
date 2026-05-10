/* NekoLang Runtime - printf wrappers for print */

#include <stdio.h>

void nekoprint_int(int val) {
    printf("%d\n", val);
}

void nekoprint_float(double val) {
    printf("%lf\n", val);
}

void nekoprint_char(char val) {
    printf("%c\n", val);
}

void nekoprint_bool(_Bool val) {
    printf("%s\n", val ? "true" : "false");
}
