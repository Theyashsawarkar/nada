// Text that follows the phone's font size, but only so far: past 1.15× the
// layout (cards, rows, the tab bar) would break.
import { Text as RNText, type TextProps } from "react-native";

export function Text(props: TextProps) {
  return <RNText maxFontSizeMultiplier={1.15} {...props} />;
}
