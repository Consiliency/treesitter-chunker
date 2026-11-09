#include "tree_sitter/parser.h"
int tree_sitter_repro_parse(int v) { return ts_repro_check(v) + 1; }
const char *tree_sitter_repro_parser_where(void) { return ts_repro_header_file(); }
