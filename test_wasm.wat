(module
  ;; Import memory from the host
  (import "env" "memory" (memory 1))
  
  ;; Import print function from host
  (import "env" "print" (func $print (param i32)))
  
  ;; Function to add two numbers
  (func $add (param $a i32) (param $b i32) (result i32)
    (local.get $a)
    (local.get $b)
    (i32.add)
  )
  
  ;; Function to multiply two numbers
  (func $multiply (param $a i32) (param $b i32) (result i32)
    (local.get $a)
    (local.get $b)
    (i32.mul)
  )
  
  ;; Function to calculate factorial
  (func $factorial (param $n i32) (result i32)
    (if (result i32)
      (i32.le_s (local.get $n) (i32.const 1))
      (then (i32.const 1))
      (else
        (local.get $n)
        (local.get $n)
        (i32.const 1)
        (i32.sub)
        (call $factorial)
        (call $multiply)
      )
    )
  )
  
  ;; Export functions so they can be called from host
  (export "add" (func $add))
  (export "multiply" (func $multiply))
  (export "factorial" (func $factorial))
)
