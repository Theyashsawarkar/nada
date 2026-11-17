/** Debug logs: `adb logcat -s ReactNativeJS | grep nada`. */
export function log(...args: unknown[]): void {
  console.log("nada:", ...args.map((a) => (a instanceof Error ? a.message : a)));
}
