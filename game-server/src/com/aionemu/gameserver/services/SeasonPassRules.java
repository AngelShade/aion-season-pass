package com.aionemu.gameserver.services;

import java.time.*;
import java.time.temporal.TemporalAdjusters;

/** Pure season rules shared by gameplay, purchases and the window. */
public final class SeasonPassRules {

	public enum Cadence { DAILY, WEEKLY, SEASON }
	public enum Event { LOGIN, HUNT, QUEST, GATHER, MINUTE, ELITE, CRAFT, PVP }
	public record Mission(String id, Cadence cadence, Event event, int target, int xp, String name, String description) {}
	public enum ClassBundle { NONE, NORMAL, GREATER, MAJOR }
	public record Reward(int level, int track, int item, long count, String name, String description, ClassBundle classBundle) {}
	/** Existing native boxes are consecutive in this explicit class order. Base classes must ascend first. */
	public static int classBundleItem(ClassBundle bundle, String playerClass) {
		int offset = switch (playerClass) {
			case "GLADIATOR" -> 0; case "TEMPLAR" -> 1; case "ASSASSIN" -> 2; case "RANGER" -> 3;
			case "SORCERER" -> 4; case "SPIRIT_MASTER" -> 5; case "CLERIC" -> 6; case "CHANTER" -> 7;
			case "GUNNER" -> 8; case "RIDER" -> 9; case "BARD" -> 10; default -> -1;
		};
		return bundle == ClassBundle.NONE || offset < 0 ? 0 : (switch (bundle) {
			case NORMAL -> 188053750; case GREATER -> 188053761; case MAJOR -> 188053772; default -> 0;
		}) + offset;
	}
	public record Season(String id, String serverName, String name, String subtitle, ZoneId zone, Instant starts, Instant ends, Instant claimsEnd,
		int levels, int xpPerLevel, long premiumKinah, long advancedKinah, int advancedLevels) {
		public boolean active(Instant now) { return !now.isBefore(starts) && now.isBefore(ends); }
		public boolean claimable(Instant now) { return !now.isBefore(starts) && now.isBefore(claimsEnd); }
		public int maxXp() { return Math.multiplyExact(levels, xpPerLevel); }
		public int level(int xp) { return Math.min(levels, Math.max(0, xp) / xpPerLevel); }
	}
	public record Upgrade(long cost, int xp, boolean boost) {}

	private SeasonPassRules() {}
	public static String period(Mission m, Season s, Instant now) {
		LocalDate day = now.atZone(s.zone()).toLocalDate();
		return switch (m.cadence()) {
			case DAILY -> day.toString();
			case WEEKLY -> day.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)).toString();
			case SEASON -> s.id();
		};
	}
	public static Instant reset(Mission m, Season s, Instant now) {
		LocalDate day = now.atZone(s.zone()).toLocalDate();
		Instant end = switch (m.cadence()) {
			case DAILY -> day.plusDays(1).atStartOfDay(s.zone()).toInstant();
			case WEEKLY -> day.with(TemporalAdjusters.next(DayOfWeek.MONDAY)).atStartOfDay(s.zone()).toInstant();
			case SEASON -> s.ends();
		};
		return end.isBefore(s.ends()) ? end : s.ends();
	}
	public static Upgrade upgrade(Season s, int currentTier, int target, int xp, boolean boosted, Instant now) {
		if (!s.active(now)) throw new IllegalArgumentException("Purchases close when the season ends.");
		if (target < 1 || target > 2 || currentTier < 0 || currentTier >= target)
			throw new IllegalArgumentException("That pass is already owned or cannot be selected.");
		long cost = (target == 2 ? s.advancedKinah() : s.premiumKinah()) - (currentTier == 1 ? s.premiumKinah() : 0);
		boolean boost = target == 2 && !boosted;
		int next = (int)Math.min(s.maxXp(), (long)xp + (boost ? (long)s.advancedLevels() * s.xpPerLevel() : 0));
		return new Upgrade(cost, next, boosted || boost);
	}
	public static boolean canClaim(Season s, Reward r, int tier, int xp, boolean claimed, Instant now) {
		return s.claimable(now) && !claimed && r.track() <= tier && r.level() <= s.level(xp);
	}
}
