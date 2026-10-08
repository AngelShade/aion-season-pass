package com.aionemu.gameserver.model.account;

/**
 * @author nrg
 */
public class CharacterBanInfo {

	private final long start;
	private final long end;
	private final String reason;

	public CharacterBanInfo(long start, long duration, String reason) {
		this.start = start;
		this.end = duration + start;
		this.reason = reason;
	}

	public long getStart() {
		return start;
	}

	public long getEnd() {
		return end;
	}

	public String getReason() {
		return reason;
	}
}
