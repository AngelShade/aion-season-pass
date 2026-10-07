# Ascendant Dawn reward catalog

This is a server-configured Aetherfall season, not an official NCsoft season.
It uses existing matching 4.8 items, native icons, item stats, box contents and
selection behavior. There are 90 slots and no serum or dye filler.

## Track totals

Paid columns list the additional rewards on that track. Premium also includes
Free; Advanced also includes Free and Premium. Every item still requires its
season level. The ten-level Advanced boost is applied once.

| Reward | Free | Premium additional | Advanced additional |
| --- | ---: | ---: | ---: |
| Omega Enchantment Stone | 1 | 4 | 8 |
| Event Tempering Solution | 4 | 4 | 12 |
| Composite manastone choice bundles | 6 | 12 | 12 |
| Event Ceramium Medal Boxes | 4 | 8 | 12 |
| Assured Greater Felicitous Socketing (Mythic) | 0 | 8 | 17 |
| Chargeable normal stigma bundles | 2 | 2 | 0 |
| Chargeable greater stigma bundles | 1 | 2 | 2 |
| Chargeable major stigma bundles | 0 | 2 | 2 |
| Empyrean Plume choice chests | 1 | 0 | 2 |
| Ancient Coins / Blood Marks | 160 / 60 | 0 | 0 |
| Event appearance | Dragon Lord wings, level 30 | Dynasty Light Armor, level 15 | Dynasty Heavy Armor, level 15 |
| Travel / utility | — | Bound Gyrocopter, level 25; permanent Stormwing pet, level 30 | — |
| Level-65 Mythic weapon / shield choice | — | — | Nether Dragon King's Sealed Box, level 30 |

At all three tracks' completion, a character receives 13 Omega stones, 20
Tempering Solutions, 30 composite choices, 25 Mythic socketing aids, 13
class-matched stigma bundles, three plume choices and 24 medal boxes, alongside
the capstones. Medal boxes give 1–3 medals each, so the cumulative range is
24–72; the top number is not guaranteed.

## Why these rewards help

The official June 2015 [Upheaval patch notes](https://static.ncsoft.com/aion/store/PatchNotes/AION_Patch_Notes_061715.pdf),
Stigma Changes, describe chargeable stigmas as rare instance drops and charging
as consuming matching copies, with failure risks. Therefore the catalog gives
the existing normal/greater/major chargeable stigma bundles for the character's
advanced class, rather than modern-version Stigma Enchantment Stones or random
other-class stigmas. A bundle rolls one native stigma; it does not guarantee
the precise duplicate a player needs. Existing faction-specific versions and
shared skills are retained. Base classes must ascend before claiming these
slots; Claim Available skips them meanwhile.

Composite choices let players select relevant physical, magical or defensive
stats instead of receiving unsuitable random manastones. Mythic socketing aids
reduce losses while socketing eligible equipment. Omega stones and Tempering
Solutions support equipment and accessory/plume progression, with native
failure rules preserved. Coins and medals contribute toward merchant equipment;
they do not grant Abyss Points or override rank requirements. Plume choices offer
Attack or Magic Boost for the player's own faction. Stormwing provides permanent
auto-looting and automatic food/scroll use; the Gyrocopter is the character-bound
native edition. The Advanced finale is actual level-65 Mythic equipment, not a
renamed cosmetic weapon. No item stats are increased for this pass.

The publisher's archived [Steam announcements](https://steamcommunity.com/app/373680/allnews/)
show event reward families including Omega stones, Tempering Solutions,
Empyrean Plumes, composite manastones, stigmas, Mythic weapons and mounts.
These announcements span more than one patch; their dates alone do not prove
an item belongs to 4.8. Compatibility here is established from the matching
local client item definitions and native icon catalog. Exact farming hours and
official historical drop probabilities are not claimed.

## Box provenance and empty entries

The Ascendant Dawn reward pools retain their existing contents. Sixteen separate
empty native box IDs have now been restored from exact-ID online tables, checked
against the 4.8 client. See [restoration evidence and opening behavior](RESTORED_REWARD_BOXES.md).
The detailed odds are published Codex US data; historical official 4.8 odds are
not independently certified.

| Native box | Existing behavior retained |
| --- | --- |
| 188052741 Brilliant Composite Manastone Bundle | Choose one of 18 level-60 composite manastones |
| 188053321 Empyrean Plume Chest | Choose one of two plumes for the character's faction |
| 188053666 Ceramium Medal Box | One item entry, quantity 1–3 |
| 188052319 Dragon Lord's Wing Box | Tiamat's Spectral Wings; level 60, 85 flight seconds, native secondary stats |
| 188053750–188053760 | Normal chargeable stigma bundles, eleven advanced classes |
| 188053761–188053771 | Greater chargeable stigma bundles, same class order |
| 188053772–188053782 | Major chargeable stigma bundles, same class order |
| 188053646 Nether Dragon King's Sealed Box | Choose from 13 Mythic weapon types and one shield |

The original `Data/Items/Items.pak` and English tooltip archives were inspected.
They confirm item IDs, native names, levels, event editions and opening behavior.
The original empty IDs 188052187, 188052555, 188053068, 188053975, 188053976 and
188053979-188053989 now have their own native random definitions. No replacement
item IDs were used, and the season's published reward slots remain stable.

The reward dialog previews existing box contents with native icons and clearly
distinguishes choice boxes, random stigma rolls and fixed contents. Selection
still occurs in the original in-game box window after mail collection.

## Event editions and season availability

The selected Dynasty event IDs, bound Gyrocopter ID, Stormwing event egg and
Nether Dragon King box are absent from the configured Central Market TSVs and
from other direct static acquisition mappings checked in this catalog audit.
Related boxes can still contain them, and normal editions can share appearances.
Therefore the UI calls them native event editions, not unique new skins or
globally exclusive items. Their pass acquisition closes with this season's claim
deadline; already collected items are permanent. Future seasons have no automatic
catalog or guaranteed repeated capstones.

Run `python client-mods/season-pass/verify_rewards.py` to validate the 90 slots,
all 33 native class bundles, usable class/faction stigma variants, nonempty boxes,
quantity ranges, native icons, plume options, Mythic choices and pet permanence.
The server refuses an empty configured reward box at startup. Staging/installation
also verify that deployed item, box and pet data match the checked catalog.
