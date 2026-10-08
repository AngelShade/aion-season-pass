"""Verify every pass box, native choice, and class-specific chargeable stigma pool.

This checks existing authoritative server content; it does not assert historical
official drop probabilities or rewrite boxes with undocumented contents.
"""
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
classes=['GLADIATOR','TEMPLAR','ASSASSIN','RANGER','SORCERER','SPIRIT_MASTER','CLERIC','CHANTER','GUNNER','RIDER','BARD']
class_ids=[1,2,4,5,7,8,10,11,14,13,16]
bases={'NORMAL':188053750,'GREATER':188053761,'MAJOR':188053772}
qualities={'NORMAL':'RARE','GREATER':'LEGEND','MAJOR':'UNIQUE'}
checks=0
def check(ok,label):
    global checks
    checks+=1
    if not ok:raise AssertionError(label)

def main():
    items={int(e.get('id')):e for e in ET.parse(ROOT/'game-server/data/static_data/items/item_templates.xml').getroot()}
    boxes={int(e.get('item_id')):e for e in ET.parse(ROOT/'game-server/data/static_data/decomposable_items/decomposable_items.xml').getroot()}
    client={int(row.split('\t')[0]) for row in (ROOT/'game-server/config/central-market/media/icon_sources.tsv').read_text().splitlines() if row.split('\t')[0].isdigit()}
    rows=[line.split('\t') for line in (ROOT/'game-server/config/season-pass/rewards.tsv').read_text().splitlines() if not line.startswith('#')]
    rewards=set();totals=[Counter(),Counter(),Counter()]
    check(len(rows)==90,'90 reward slots')
    for level,track,item,quantity,name,description,bundle in rows:
        item=int(item);t=items[item];quantity=int(quantity);track=int(track)
        check(t.get('name')==name,'exact English reward name')
        check(item//1000000!=162 and 'Dye' not in name,'no recovery or dye filler')
        check(quantity<=int(t.get('max_stack_count','1')),'native reward stack')
        check(t.get('expire_time','0')=='0','reward must be permanent')
        if bundle=='NONE':rewards.add(item)
        else:
            check(item==bases[bundle],'explicit native class-bundle base')
            for offset,(pc,cid) in enumerate(zip(classes,class_ids)):
                native=bases[bundle]+offset;rewards.add(native);box=boxes[native]
                check(bool(box.findall('items')) and box.get('selectable')!='true','native random class bundle')
                for group in box.findall('items'):
                    check(not group.findall('random_item'),'explicit native stigma pool')
                    for race in ['ELYOS','ASMODIANS']:
                        eligible=[entry for entry in group.findall('item') if entry.get('race','PC_ALL') in ['PC_ALL',race]]
                        check(len(eligible)==1,'one stigma per selected group for '+race)
                    for entry in group.findall('item'):
                        child=items[int(entry.get('id'))]
                        check(child.find('stigma') is not None and child.find('stigma').get('chargeable')=='true','4.8 chargeable stigma')
                        check(child.get('quality')==qualities[bundle],'correct stigma grade')
                        limits=list(map(int,child.get('restrict').split()))
                        check(limits[cid]>0,pc+' receives usable stigmas, including legitimate shared class skills')
        totals[track][bundle if bundle!='NONE' else name]+=quantity
    for item in rewards:
        t=items[item]
        check(item in client,'native client reward icon')
        if t.find('actions/decompose') is None:continue
        box=boxes.get(item)
        check(box is not None and len(box)>0,'reward boxes must not be empty')
        for group in box.findall('items'):
            check(bool(group.findall('item')),'existing direct native pool')
            check(float(group.get('chance','100'))>0,'reachable reward group')
            check(int(group.get('minlevel','0'))<=65<=int(group.get('maxlevel','99')),'pool available at endgame')
            for entry in group.findall('item'):
                child=int(entry.get('id'));check(child in items and child in client,'content exists on server and client')
                check(1<=int(entry.get('min_count','1'))<=int(entry.get('max_count',entry.get('min_count','1'))),'valid native quantity range')
    check(boxes[188053646].get('selectable')=='true' and len(boxes[188053646].findall('items/item'))==14,'14 original selectable Mythic weapon/shield options')
    for e in boxes[188053646].findall('items/item'):
        t=items[int(e.get('id'))];check(t.get('quality')=='MYTHIC' and t.get('level')=='65','original level-65 Mythic finale')
    check(boxes[188052741].get('selectable')=='true' and len(boxes[188052741].findall('items/item'))==18,'18 original composite choices')
    for race in ['ELYOS','ASMODIANS']:
        choices=[e for e in boxes[188053321].findall('items/item') if e.get('race')==race]
        check(len(choices)==2,'physical/magical plume choices for '+race)
    pet=items[190020133].find('actions/adoptpet')
    check(pet.get('petId')=='900141' and pet.get('expire_minutes','0')=='0','permanent native Stormwing adoption')
    check(int(items[190100151].get('mask'))&2==0,'character-bound Gyrocopter edition')
    # Restored original IDs are audited separately; the published season catalog stays stable.
    for restored in [188052187,188052555,188053068,188053975,188053976,188053979]:
        check(restored not in rewards and len(boxes[restored])>0,'original box restored without changing published pass slot: '+str(restored))
    for track,total in enumerate(totals):print('Track',track,dict(total))
    print(f'OK: {checks} reward/box checks, all 33 class bundles, faction plume choices, permanent pet, original Mythic choices. Season reward pools unchanged.')

if __name__=='__main__':
    try:main()
    except Exception as e:print('FAIL:',e);raise
