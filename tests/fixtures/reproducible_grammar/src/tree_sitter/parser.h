#include <assert.h>
static inline int ts_repro_check(int v) { assert(v >= 0); return v * 2; }
static inline const char *ts_repro_header_file(void) { return __FILE__; }
