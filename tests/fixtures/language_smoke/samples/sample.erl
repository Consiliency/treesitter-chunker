-module(sample).
-export([greet/1, add/2]).

greet(Name) ->
    "hi " ++ Name.

add(A, B) ->
    A + B.
