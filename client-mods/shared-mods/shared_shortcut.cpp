#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstring>
#include <cmath>
#include <initializer_list>
using Ptr=void*;
extern "C" __declspec(dllexport) volatile DWORD AionMarketDiagnostics[4]={3,0,0,0};
template<class T> T method(Ptr o,size_t n){return reinterpret_cast<T>((*reinterpret_cast<void***>(o))[n/8]);}
unsigned char* game(){return reinterpret_cast<unsigned char*>(GetModuleHandleW(L"Game.dll"));}
struct Rect { double x,y,w,h; };
Ptr find(Ptr dialog,const char* name,int type){return method<Ptr(*)(Ptr,const char*,int)>(dialog,0x338)(dialog,name,type);}
extern "C" __declspec(dllexport) int AionMarketCommand(Ptr,Ptr event) {
    if (!event) return 0;
    Ptr button=*static_cast<Ptr*>(event); if (!button) return 0;
    const char* name=method<const char*(*)(Ptr)>(button,0xa8)(button); if (!name) return 0;
    const char* command=nullptr;
    if (!std::strcmp(name,"season_pass_button")) command="/seasonpass";
    if (!std::strcmp(name,"central_market_button")) command="/centralmarket";
    if (!command) return 0;
    ++AionMarketDiagnostics[3];
    reinterpret_cast<int(*)(const char*)>(game()+0x628270)(command); return 1;
}
extern "C" __declspec(dllexport) void AionMarketLayout(Ptr dialog) {
    if (!dialog) return;
    ++AionMarketDiagnostics[1];
    Ptr container=find(dialog,"item_shop_container",0x2008); if (!container) return;
    Ptr shop=nullptr;
    for (auto name:{"item_ingame_web_shop","item_shop_gf","item_shop"}) {
        Ptr candidate=find(dialog,name,0x2001);
        if (candidate && (method<int(*)(Ptr)>(candidate,0xb8)(candidate)&1)) {shop=candidate;break;}
    }
    if (!shop) shop=find(dialog,"item_ingame_web_shop",0x2001);
    if (!shop) return;
    auto parent=*reinterpret_cast<Rect*>(static_cast<unsigned char*>(container)+0x50);
    auto anchor=*reinterpret_cast<Rect*>(static_cast<unsigned char*>(shop)+0x50);
    double scale=*reinterpret_cast<double*>(game()+0x1378ec8);
    if (!std::isfinite(scale) || scale<=0 || scale>4) return;
    const char* names[]={"central_market_button","season_pass_button"};
    for (int index=0;index<2;++index) {
        Ptr button=find(dialog,names[index],0x2001);if(!button)continue;
        Rect desired={parent.x+anchor.x-(40+40*index)*scale,parent.y+anchor.y,34*scale,(index==0?36:32)*scale};
        auto current=*reinterpret_cast<Rect*>(static_cast<unsigned char*>(button)+0x50);
        if (std::memcmp(&desired,&current,sizeof desired)) {
            method<void(*)(Ptr,const Rect*)>(button,0x1a8)(button,&desired);++AionMarketDiagnostics[2];
        }
    }
}
