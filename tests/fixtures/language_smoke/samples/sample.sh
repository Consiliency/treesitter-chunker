greet() {
  echo "hi $1"
}

add() {
  echo $(( $1 + $2 ))
}

greet world
