package main

import "testing"

func TestGreet(t *testing.T) {
	got := greet("world")
	want := "Hello from world"
	if got != want {
		t.Errorf("greet(\"world\") = %q, want %q", got, want)
	}
}
