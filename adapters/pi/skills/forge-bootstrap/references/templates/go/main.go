package main

import "fmt"

// greet returns the project greeting for name.
func greet(name string) string {
	return "Hello from " + name
}

func main() {
	fmt.Println(greet("{{PROJECT_NAME}}"))
}
