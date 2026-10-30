/* Level 135: the C program that calls your functions. It reads a test case from
 * stdin and prints what your functions return. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int64_t dot(const int64_t *a, const int64_t *b, size_t n);
int cmp_desc(const void *x, const void *y);
size_t count_char(const char *s, int c);

int main(void) {
    size_t n;
    if (scanf("%zu", &n) != 1 || n > 1000) return 2;
    int64_t *a = malloc((n + 1) * sizeof *a), *b = malloc((n + 1) * sizeof *b);
    for (size_t i = 0; i < n; i++) scanf("%ld", &a[i]);
    for (size_t i = 0; i < n; i++) scanf("%ld", &b[i]);
    char text[256];
    int c;
    if (scanf(" %255[^\n] %d", text, &c) != 2) return 2;

    printf("dot = %ld\n", dot(a, b, n));
    qsort(a, n, sizeof *a, cmp_desc);
    printf("sorted =");
    for (size_t i = 0; i < n; i++) printf(" %ld", a[i]);
    printf("\ncount = %zu\n", count_char(text, c));
    free(a);
    free(b);
    return 0;
}
