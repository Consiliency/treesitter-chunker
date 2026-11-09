#include <assert.h>
#include "tree_sitter/parser.h"
int tree_sitter_repro_scan(int v) { assert(v != 42); return ts_repro_check(v) - 1; }
const char *tree_sitter_repro_where(void) { return ts_repro_header_file()[0] ? __FILE__ : ""; }
