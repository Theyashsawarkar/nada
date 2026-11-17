import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ScrollView, View } from "react-native";
import { Text } from "../../ui/text";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";
import { hourName, week, type Week } from "../../core/insights";
import { getDb, now } from "../../core/store";
import { Aurora, POOLS } from "../../ui/aurora";
import { Icon } from "../../ui/icons";
import { Card, Empty, Tag, s } from "../../ui/parts";
import { BOTTOM, c, f } from "../../ui/theme";

function duration(min: number): string {
  return min >= 60 ? `${Math.floor(min / 60)}h ${min % 60}m` : `${min}m`;
}

/** The 24-hour listening clock: one segment per hour, longer and pinker the more you listened. */
function ListenClock({ hours }: { hours: number[] }) {
  const max = Math.max(1, ...hours);
  const cx = 60, r1 = 36, r2 = 56;
  const pt = (a: number, rr: number) => `${(cx + Math.cos(a) * rr).toFixed(1)} ${(cx + Math.sin(a) * rr).toFixed(1)}`;
  return (
    <Svg width={118} height={118} viewBox="0 0 120 120">
      {hours.map((m, i) => {
        const a0 = (i / 24) * Math.PI * 2 - Math.PI / 2 + 0.03;
        const a1 = ((i + 1) / 24) * Math.PI * 2 - Math.PI / 2 - 0.03;
        const hot = m / max;
        const rr = r1 + 4 + (r2 - r1 - 4) * hot;
        const col = hot > 0.7 ? c.accent : hot > 0.35 ? c.mauve : c.sky;
        return <Path key={i} d={`M${pt(a0, r1)} L${pt(a0, rr)} A${rr} ${rr} 0 0 1 ${pt(a1, rr)} L${pt(a1, r1)} A${r1} ${r1} 0 0 0 ${pt(a0, r1)}Z`}
          fill={col} opacity={0.3 + hot * 0.7} />;
      })}
      <Circle cx={60} cy={60} r={33} fill="none" stroke="rgba(255,255,255,0.08)" />
    </Svg>
  );
}

const MOOD = [c.accent, c.mauve, c.sky, c.teal];

export default function Insights() {
  const insets = useSafeAreaInsets();
  const [w, setW] = useState<Week | null>(null);
  useFocusEffect(useCallback(() => setW(week(getDb(), now())), []));
  if (!w) return <View style={s.screen} />;
  const maxDay = Math.max(1, ...w.daily);

  return (
    <View style={s.screen}>
      <Aurora pools={POOLS.insights!} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingTop: insets.top + 12, paddingHorizontal: 18, paddingBottom: BOTTOM }}>
      <Text style={s.h1}>Your sound</Text>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10, padding: 10, borderRadius: 14,
        backgroundColor: "rgba(166,227,161,0.08)", borderWidth: 1, borderColor: "rgba(166,227,161,0.25)" }}>
        <Icon name="lock" size={15} color={c.green} />
        <Text style={{ color: c.green, fontFamily: f.body, fontSize: 12, flex: 1 }}>Worked out on this phone, from your history. Never uploaded.</Text>
      </View>

      {w.minutes === 0 && w.streak === 0 ? (
        <Empty title="Nothing to show yet" body="Listen for a few days and this shows when you listen, what you play most, and how it changes week to week." />
      ) : (
        <>
          <View style={{ flexDirection: "row", gap: 10, marginTop: 12 }}>
            <Card style={{ flex: 1, padding: 13 }}>
              <Text style={{ color: c.text, fontFamily: f.displayBold, fontSize: 22 }}>{duration(w.minutes)}</Text>
              <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11 }}>listened this week</Text>
              {w.change !== null ? (
                <Text style={{ color: w.change >= 0 ? c.green : c.peach, fontFamily: f.medium, fontSize: 11, marginTop: 3 }}>
                  {w.change >= 0 ? "↑" : "↓"} {Math.abs(Math.round(w.change * 100))}% on last week
                </Text>
              ) : null}
            </Card>
            <Card style={{ flex: 1, padding: 13 }}>
              <Text style={{ color: c.text, fontFamily: f.displayBold, fontSize: 22 }}>{w.streak} {w.streak === 1 ? "day" : "days"}</Text>
              <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11 }}>in a row</Text>
              <Text style={{ color: c.green, fontFamily: f.medium, fontSize: 11, marginTop: 3 }}>best: {w.bestStreak}</Text>
            </Card>
          </View>

          <Card style={{ marginTop: 10, padding: 13, flexDirection: "row", gap: 14, alignItems: "center" }}>
            <View style={{ width: 118, height: 118, alignItems: "center", justifyContent: "center" }}>
              <ListenClock hours={w.hours} />
              <View style={{ position: "absolute", alignItems: "center" }}>
                <Text style={{ color: c.text, fontFamily: f.display, fontSize: 16 }}>{w.topHour !== null ? hourName(w.topHour) : "–"}</Text>
                <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 10.5 }}>your hour</Text>
              </View>
            </View>
            <View style={{ flex: 1, gap: 8 }}>
              {w.moods.length ? w.moods.map((m, i) => (
                <View key={m.name}>
                  <Text style={{ color: c.text, fontFamily: f.body, fontSize: 11.5 }}>{m.name}</Text>
                  <View style={{ height: 6, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.08)", marginTop: 3 }}>
                    <View style={{ width: `${Math.round(m.share * 100)}%`, height: 6, borderRadius: 4, backgroundColor: MOOD[i % MOOD.length] }} />
                  </View>
                </View>
              )) : <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12 }}>The ring is a 24-hour clock of when you listen.</Text>}
            </View>
          </Card>

          {w.topArtist ? (
            <Card style={{ marginTop: 10, padding: 12, flexDirection: "row", alignItems: "center", gap: 10 }}>
              <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: c.mauve, alignItems: "center", justifyContent: "center" }}>
                <Text style={{ color: c.crust, fontFamily: f.displayBold, fontSize: 17 }}>{w.topArtist.name.slice(0, 1)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11 }}>Top artist this week</Text>
                <Text style={{ color: c.text, fontFamily: f.semibold, fontSize: 14 }}>{w.topArtist.name}</Text>
                <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 11.5 }}>
                  {duration(w.topArtist.minutes)} · {w.topArtist.plays} plays · {w.topArtist.songs} songs
                </Text>
              </View>
              {w.topArtist.newNumberOne ? <Tag color={c.peach}>new #1</Tag> : null}
            </Card>
          ) : null}

          <Card style={{ marginTop: 10, padding: 13 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: c.text, fontFamily: f.semibold, fontSize: 12 }}>Every day</Text>
              <Text style={{ color: c.muted, fontFamily: f.body, fontSize: 12 }}>minutes</Text>
            </View>
            <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 6, height: 60, marginTop: 8 }}>
              {w.daily.map((m, i) => (
                <View key={i} style={{ flex: 1, alignItems: "center", gap: 4 }}>
                  <View style={{ width: "100%", height: Math.max(3, (m / maxDay) * 46), borderRadius: 4,
                    backgroundColor: i === 6 ? c.accent : c.mauve, opacity: i === 6 ? 1 : 0.6 }} />
                </View>
              ))}
            </View>
          </Card>
        </>
      )}
      </ScrollView>
    </View>
  );
}
