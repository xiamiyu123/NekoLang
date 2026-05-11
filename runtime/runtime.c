/* NekoLang Runtime - printing, argv parsing, and basic file I/O */

#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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

static void runtime_fail(const char *message, const char *detail) {
    if (detail) {
        fprintf(stderr, "runtime error: %s: %s\n", message, detail);
    } else {
        fprintf(stderr, "runtime error: %s\n", message);
    }
    exit(1);
}

static int runtime_arg_index(int argc, int index) {
    int actual = index + 1;
    if (index < 0 || actual >= argc) {
        runtime_fail("argv index out of range", NULL);
    }
    return actual;
}

static FILE *runtime_open_read(const char *path) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        runtime_fail("failed to open file for reading", path);
    }
    return fp;
}

static FILE *runtime_open_write(const char *path) {
    FILE *fp = fopen(path, "w");
    if (!fp) {
        runtime_fail("failed to open file for writing", path);
    }
    return fp;
}

static void runtime_expect(int ok, const char *message, const char *detail) {
    if (!ok) {
        runtime_fail(message, detail);
    }
}

int neko_argv_int(int argc, char **argv, int index) {
    int actual = runtime_arg_index(argc, index);
    char *end = NULL;
    long value = strtol(argv[actual], &end, 10);
    runtime_expect(end && *end == '\0', "argv-int parse failed", argv[actual]);
    return (int)value;
}

double neko_argv_float(int argc, char **argv, int index) {
    int actual = runtime_arg_index(argc, index);
    char *end = NULL;
    double value = strtod(argv[actual], &end);
    runtime_expect(end && *end == '\0', "argv-float parse failed", argv[actual]);
    return value;
}

char neko_argv_char(int argc, char **argv, int index) {
    int actual = runtime_arg_index(argc, index);
    runtime_expect(argv[actual][0] != '\0', "argv-char requires a non-empty argument", NULL);
    return argv[actual][0];
}

_Bool neko_argv_bool(int argc, char **argv, int index) {
    int actual = runtime_arg_index(argc, index);
    if (strcmp(argv[actual], "true") == 0) {
        return 1;
    }
    if (strcmp(argv[actual], "false") == 0) {
        return 0;
    }
    runtime_fail("argv-bool parse failed", argv[actual]);
    return 0;
}

int neko_read_int(const char *path) {
    int value = 0;
    FILE *fp = runtime_open_read(path);
    runtime_expect(fscanf(fp, "%d", &value) == 1, "read-int failed", path);
    fclose(fp);
    return value;
}

double neko_read_float(const char *path) {
    double value = 0.0;
    FILE *fp = runtime_open_read(path);
    runtime_expect(fscanf(fp, "%lf", &value) == 1, "read-float failed", path);
    fclose(fp);
    return value;
}

char neko_read_char(const char *path) {
    int value = 0;
    FILE *fp = runtime_open_read(path);
    do {
        value = fgetc(fp);
    } while (value != EOF && isspace(value));
    fclose(fp);
    runtime_expect(value != EOF, "read-char failed", path);
    return (char)value;
}

_Bool neko_read_bool(const char *path) {
    char buffer[16] = {0};
    FILE *fp = runtime_open_read(path);
    runtime_expect(fscanf(fp, "%15s", buffer) == 1, "read-bool failed", path);
    fclose(fp);
    if (strcmp(buffer, "true") == 0) {
        return 1;
    }
    if (strcmp(buffer, "false") == 0) {
        return 0;
    }
    runtime_fail("read-bool parse failed", path);
    return 0;
}

void neko_write_int(const char *path, int value) {
    FILE *fp = runtime_open_write(path);
    fprintf(fp, "%d\n", value);
    fclose(fp);
}

void neko_write_float(const char *path, double value) {
    FILE *fp = runtime_open_write(path);
    fprintf(fp, "%lf\n", value);
    fclose(fp);
}

void neko_write_char(const char *path, char value) {
    FILE *fp = runtime_open_write(path);
    fprintf(fp, "%c\n", value);
    fclose(fp);
}

void neko_write_bool(const char *path, _Bool value) {
    FILE *fp = runtime_open_write(path);
    fprintf(fp, "%s\n", value ? "true" : "false");
    fclose(fp);
}
