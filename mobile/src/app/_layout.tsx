import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold } from "@expo-google-fonts/inter";
import { SpaceGrotesk_600SemiBold, SpaceGrotesk_700Bold } from "@expo-google-fonts/space-grotesk";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { getDb } from "../core/store";
import { resumeDownloads } from "../player/downloads";
import { c } from "../ui/theme";

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function Root() {
  const [fonts] = useFonts({ Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold, SpaceGrotesk_600SemiBold, SpaceGrotesk_700Bold });
  useEffect(() => {
    getDb();
    resumeDownloads();
    SystemUI.setBackgroundColorAsync(c.bg).catch(() => {});
  }, []);
  useEffect(() => {
    if (fonts) SplashScreen.hideAsync().catch(() => {});
  }, [fonts]);
  if (!fonts) return null;
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: c.bg }}>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg }, animation: "fade" }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="player" options={{ presentation: "modal", animation: "slide_from_bottom" }} />
        <Stack.Screen name="lyrics" options={{ presentation: "modal", animation: "fade" }} />
        <Stack.Screen name="queue" options={{ presentation: "modal", animation: "slide_from_bottom" }} />
      </Stack>
    </GestureHandlerRootView>
  );
}
