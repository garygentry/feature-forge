use {{PKG}}::greet;

#[test]
fn greet_returns_greeting() {
    assert_eq!(greet("world"), "Hello from world");
}
