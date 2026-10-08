package com.aionemu.gameserver.services;

import java.nio.file.Path;
import java.util.HashSet;
import javax.xml.bind.JAXBContext;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.SchemaFactory;
import com.aionemu.gameserver.dataholders.DataManager;
import com.aionemu.gameserver.dataholders.ItemData;
import com.aionemu.gameserver.dataholders.DecomposableItemsData;

/** Offline production JAXB/schema/catalog validation; no world, game client or live characters. */
public final class SeasonPassNativeDataCheck {
    public static void main(String[] args) throws Exception {
        Path source=Path.of("game-server/data/static_data");
        var validator=SchemaFactory.newInstance("http://www.w3.org/2001/XMLSchema")
            .newSchema(source.resolve("decomposable_items/decomposable_items.xsd").toFile()).newValidator();
        validator.validate(new StreamSource(source.resolve("decomposable_items/decomposable_items.xml").toFile()));
        DataManager.ITEM_DATA=(ItemData)JAXBContext.newInstance(ItemData.class).createUnmarshaller()
            .unmarshal(source.resolve("items/item_templates.xml").toFile());
        DataManager.DECOMPOSABLE_ITEMS_DATA=(DecomposableItemsData)JAXBContext.newInstance(DecomposableItemsData.class).createUnmarshaller()
            .unmarshal(source.resolve("decomposable_items/decomposable_items.xml").toFile());
        SeasonPassService.load(Path.of("game-server/config/season-pass"));
        var validate=SeasonPassService.class.getDeclaredMethod("validateRewardItem",int.class,long.class);
        validate.setAccessible(true);
        var checked=new HashSet<Integer>();
        for(var reward:SeasonPassService.rewards) {
            validate.invoke(null,reward.item(),reward.count()); checked.add(reward.item());
            if(reward.classBundle()!=SeasonPassRules.ClassBundle.NONE)
                for(String role:new String[]{"GLADIATOR","TEMPLAR","ASSASSIN","RANGER","SORCERER","SPIRIT_MASTER","CLERIC","CHANTER","GUNNER","RIDER","BARD"}) {
                    int item=SeasonPassRules.classBundleItem(reward.classBundle(),role);
                    validate.invoke(null,item,reward.count()); checked.add(item);
                }
        }
        int finale=SeasonPassService.rewards.stream().filter(r->r.level()==SeasonPassService.season.levels() && r.track()==2).findFirst().orElseThrow().item();
        var mythic=DataManager.DECOMPOSABLE_ITEMS_DATA.getSelectableItems(finale);
        if(mythic==null || mythic.size()!=14) throw new AssertionError("Native Mythic weapon/shield choices");
        System.out.println("OK: native box schema/JAXB loading and startup validation for "+checked.size()+" distinct pass/class rewards; 14 Mythic choices.");
    }
}
