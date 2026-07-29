/** Returns the project's greeting. */
export function greet(name: string = "{{PROJECT_NAME}}"): string {
  return `Hello from ${name}`;
}
