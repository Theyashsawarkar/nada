import { LinearGradient } from "expo-linear-gradient";
import { router, Tabs } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "../../ui/text";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { current, next, toggle, usePlayer } from "../../player/player";
import { Icon, type IconName } from "../../ui/icons";
import { Cover } from "../../ui/parts";
import { c, f, r } from "../../ui/theme";

const TABS: { name: string; label: string; icon: IconName }[] = [
  { name: "index", label: "Home", icon: "home" },
  { name: "search", label: "Search", icon: "search" },
  { name: "library", label: "Library", icon: "library" },
  { name: "insights", label: "Insights", icon: "insights" },
];

/** Dark glass that nothing shows through: a solid tint, a soft top
 *  highlight and a hairline edge (Android has no cheap live blur). */
function Glass({ tint }: { tint: string }) {
  return (
    <>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: tint }]} />
      <LinearGradient colors={["rgba(255,255,255,0.07)", "rgba(255,255,255,0)"]} style={StyleSheet.absoluteFill} />
    </>
  );
}

function Mini() {
  const p = usePlayer();
  const s = current();
  if (!s) return null;
  const prog = p.durationMs ? p.positionMs / p.durationMs : 0;
  return (
    <Pressable onPress={() => router.push("/player")} style={st.mini}>
      <Glass tint="#1d1830" />
      <Cover song={s} size={44} radius={13} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text numberOfLines={1} style={{ color: c.text, fontFamily: f.semibold, fontSize: 14 }}>{s.title}</Text>
        <Text numberOfLines={1} style={{ color: p.error ? c.red : c.sub, fontFamily: f.body, fontSize: 12 }}>
          {p.error ? `Couldn't play: ${p.error}` : p.buffering ? "Loading…" : s.artist_name}
        </Text>
      </View>
      <Pressable hitSlop={10} onPress={toggle} style={[st.ib, { backgroundColor: c.accent }]}><Icon name={p.playing ? "pause" : "play"} size={18} color={c.crust} /></Pressable>
      <Pressable hitSlop={10} onPress={() => void next()} style={st.ib}><Icon name="next" size={20} /></Pressable>
      <View style={st.prog}><View style={[st.progIn, { width: `${prog * 100}%` }]} /></View>
    </Pressable>
  );
}

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: c.bg } }}
      tabBar={({ state, navigateToTab }) => (
        <View style={{ position: "absolute", left: 12, right: 12, bottom: Math.max(insets.bottom, 10) + 4, gap: 10 }}>
          <Mini />
          <View style={st.nav}>
            <Glass tint="#12101c" />
            {TABS.map((t) => {
              const i = state.routes.findIndex((x) => x.name === t.name);
              const on = state.index === i;
              return (
                <Pressable key={t.name} onPress={() => state.routes[i] && navigateToTab(state.routes[i].key)} style={st.tab}>
                  <Icon name={t.icon} size={21} color={on ? c.accent : c.muted} />
                  <Text style={{ fontSize: 10.5, fontFamily: f.medium, color: on ? c.accent : c.muted }}>{t.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      )}>
      {TABS.map((t) => <Tabs.Screen key={t.name} name={t.name} />)}
    </Tabs>
  );
}

const st = StyleSheet.create({
  mini: {
    height: 62, borderRadius: 22, flexDirection: "row", alignItems: "center", gap: 11, paddingLeft: 8, paddingRight: 10,
    overflow: "hidden", borderWidth: 1, borderColor: c.line2,
  },
  ib: { width: 36, height: 36, borderRadius: r.pill, alignItems: "center", justifyContent: "center" },
  prog: { position: "absolute", left: 18, right: 18, bottom: 0, height: 2, borderRadius: 2, backgroundColor: "rgba(255,255,255,0.12)" },
  progIn: { height: 2, borderRadius: 2, backgroundColor: c.accent, shadowColor: c.accent, shadowOpacity: 0.9, shadowRadius: 6 },
  nav: {
    height: 62, borderRadius: 24, flexDirection: "row", justifyContent: "space-around", alignItems: "center",
    overflow: "hidden", borderWidth: 1, borderColor: c.line,
  },
  tab: { alignItems: "center", gap: 3, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14 },
});
