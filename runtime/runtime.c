/* NekoLang Runtime - printf wrappers for purr */

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
