/* NekoLang Runtime - printing, argv parsing, and basic file I/O */

#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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

void nekoprint_string(const char *val) {
    printf("%s\n", val);
}

void nekoprint_pointer(const void *val) {
    printf("%p\n", val);
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

static void runtime_stdin_eof(void) {
    runtime_fail("stdin reached EOF", NULL);
}

static void runtime_read_token(char *buffer, size_t size, const char *message) {
    int ok = scanf("%63s", buffer);
    if (ok == EOF) {
        runtime_stdin_eof();
    }
    runtime_expect(ok == 1, message, NULL);
    buffer[size - 1] = '\0';
}

static uint32_t runtime_rand_state = 1u;
static int runtime_rand_seeded = 0;

static void runtime_rand_ensure_seeded(void) {
    if (!runtime_rand_seeded) {
        runtime_rand_state = (uint32_t)time(NULL);
        runtime_rand_seeded = 1;
    }
}

static uint32_t runtime_rand_next(void) {
    runtime_rand_ensure_seeded();
    runtime_rand_state = runtime_rand_state * 1664525u + 1013904223u;
    return runtime_rand_state;
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

int neko_input_int(void) {
    char buffer[64] = {0};
    char *end = NULL;
    long value = 0;
    runtime_read_token(buffer, sizeof(buffer), "input-int failed");
    value = strtol(buffer, &end, 10);
    runtime_expect(end && *end == '\0', "input-int parse failed", buffer);
    return (int)value;
}

double neko_input_float(void) {
    char buffer[64] = {0};
    char *end = NULL;
    double value = 0.0;
    runtime_read_token(buffer, sizeof(buffer), "input-float failed");
    value = strtod(buffer, &end);
    runtime_expect(end && *end == '\0', "input-float parse failed", buffer);
    return value;
}

char neko_input_char(void) {
    int value = 0;
    do {
        value = getchar();
        if (value == EOF) {
            runtime_stdin_eof();
        }
    } while (isspace(value));
    return (char)value;
}

_Bool neko_input_bool(void) {
    char buffer[64] = {0};
    runtime_read_token(buffer, sizeof(buffer), "input-bool failed");
    if (strcmp(buffer, "true") == 0) {
        return 1;
    }
    if (strcmp(buffer, "false") == 0) {
        return 0;
    }
    runtime_fail("input-bool parse failed", buffer);
    return 0;
}

void neko_rand_seed(int seed) {
    runtime_rand_state = (uint32_t)seed;
    runtime_rand_seeded = 1;
}

int neko_rand_range(int low, int high) {
    uint64_t span = 0;
    uint32_t value = 0;
    runtime_expect(low <= high, "rand-range invalid bounds", NULL);
    span = (uint64_t)((int64_t)high - (int64_t)low) + 1u;
    value = runtime_rand_next();
    return low + (int)(value % span);
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

/* ── String operations ── */

static void runtime_check_string(const char *s, const char *op) {
    if (!s) {
        runtime_fail(op, "string is NULL (uninitialized?)");
    }
}

char *neko_string_concat(const char *a, const char *b) {
    runtime_check_string(a, "string concat: left operand is NULL");
    runtime_check_string(b, "string concat: right operand is NULL");
    size_t la = strlen(a);
    size_t lb = strlen(b);
    char *result = (char *)malloc(la + lb + 1);
    if (!result) {
        runtime_fail("string concat: out of memory", NULL);
    }
    memcpy(result, a, la);
    memcpy(result + la, b, lb + 1);
    return result;
}

int neko_string_length(const char *s) {
    runtime_check_string(s, "string-length: string is NULL");
    return (int)strlen(s);
}

char neko_string_at(const char *s, int i) {
    runtime_check_string(s, "string-at: string is NULL");
    int len = (int)strlen(s);
    if (i < 0 || i >= len) {
        runtime_fail("string-at: index out of range", NULL);
    }
    return s[i];
}

char *neko_string_sub(const char *s, int start, int len) {
    runtime_check_string(s, "string-sub: string is NULL");
    int slen = (int)strlen(s);
    if (start < 0 || start > slen) {
        runtime_fail("string-sub: start out of range", NULL);
    }
    if (len < 0 || start + len > slen) {
        runtime_fail("string-sub: length out of range", NULL);
    }
    char *result = (char *)malloc(len + 1);
    if (!result) {
        runtime_fail("string-sub: out of memory", NULL);
    }
    memcpy(result, s + start, len);
    result[len] = '\0';
    return result;
}

int neko_string_cmp(const char *a, const char *b) {
    runtime_check_string(a, "string-cmp: left operand is NULL");
    runtime_check_string(b, "string-cmp: right operand is NULL");
    return strcmp(a, b);
}

_Bool neko_string_contains(const char *haystack, const char *needle) {
    runtime_check_string(haystack, "string-contains: haystack is NULL");
    runtime_check_string(needle, "string-contains: needle is NULL");
    return strstr(haystack, needle) != NULL;
}

char *neko_int_to_string(int n) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%d", n);
    char *result = (char *)malloc(strlen(buf) + 1);
    if (!result) {
        runtime_fail("int-to-string: out of memory", NULL);
    }
    strcpy(result, buf);
    return result;
}

int neko_string_to_int(const char *s) {
    runtime_check_string(s, "string-to-int: string is NULL");
    char *end = NULL;
    long value = strtol(s, &end, 10);
    runtime_expect(end && *end == '\0', "string-to-int: parse failed", s);
    return (int)value;
}

char *neko_argv_string(int argc, char **argv, int index) {
    int actual = runtime_arg_index(argc, index);
    return argv[actual];
}

char *neko_char_to_string(char c) {
    char *result = (char *)malloc(2);
    if (!result) {
        runtime_fail("char-to-string: out of memory", NULL);
    }
    result[0] = c;
    result[1] = '\0';
    return result;
}

/* ── Char operations ── */

int neko_char_to_int(char c) {
    return (int)(unsigned char)c;
}

char neko_int_to_char(int n) {
    return (char)(n & 0xFF);
}

_Bool neko_is_letter(char c) {
    return isalpha((unsigned char)c) != 0;
}

_Bool neko_is_digit(char c) {
    return isdigit((unsigned char)c) != 0;
}

char neko_char_upcase(char c) {
    return (char)toupper((unsigned char)c);
}

char neko_char_downcase(char c) {
    return (char)tolower((unsigned char)c);
}
