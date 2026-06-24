<?php

class Widget
{
    public $count = 0;

    public function render()
    {
        return $this->helper($this->count);
    }

    public function helper($value)
    {
        return $value + 1;
    }
}

function run()
{
    $w = new Widget();
    return $w->render();
}
