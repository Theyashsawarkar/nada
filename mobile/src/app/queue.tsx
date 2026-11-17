import { router } from "expo-router";
import { Pressable, ScrollView, View } from "react-native";
import { Text } from "../ui/text";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { jump, usePlayer } from "../player/player";
import { Icon } from "../ui/icons";
import { songMenu } from "../ui/menu";
import { SongRow } from "../ui/parts";
import { c, f } from "../ui/theme";

export default function Queue() {
  const insets = useSafeAreaInsets();
  const p = usePlayer();
  const upcoming = p.queue.slice(p.index + 1);
  return (
    <View style={{ flex: 1, backgroundColor: c.bg2 }}>
      <View style={{ paddingTop: insets.top + 8, paddingHorizontal: 20, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Pressable hitSlop={12} onPress={() => router.back()}><Icon name="chevron" size={24} /></Pressable>
        <Text style={{ color: c.text, fontFamily: f.display, fontSize: 17 }}>Up next</Text>
        <View style={{ width: 24 }} />
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 12, paddingBottom: insets.bottom + 30 }}>
        <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12.5, marginBottom: 10 }}>
          {upcoming.length ? `${upcoming.length} songs from ${p.source || "your queue"}. When they run out, more like the last one play by themselves.`
            : "When this song ends, more like it play by themselves."}
        </Text>
        {upcoming.map((song, i) => (
          <SongRow key={`${song.id}-${i}`} song={song} onPress={() => jump(p.index + 1 + i)} onMore={() => songMenu(song)} />
        ))}
      </ScrollView>
    </View>
  );
}
