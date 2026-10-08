package com.aionemu.gameserver.model.gameobjects.player;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * @author Aquanox, nrg
 */
public class Macros {

	private final Map<Integer, Macro> macrosById = new HashMap<>(12);

	public synchronized List<Macro> getAll() {
		return new ArrayList<>(macrosById.values());
	}

	/**
	 * @return <tt>true</tt> if given macro ID was not used before.
	 */
	public synchronized boolean add(int macroId, String macroXML) {
		if (macroId < 1 || macroId > 12)
			throw new IllegalArgumentException("Invalid macro ID: " + macroId);
		return macrosById.put(macroId, new Macro(macroId, macroXML)) == null;
	}

	public synchronized boolean remove(int macroId) {
		return macrosById.remove(macroId) != null;
	}

	public record Macro(int id, String xml) {}
}
