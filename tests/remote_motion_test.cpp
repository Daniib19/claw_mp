#include "../OpenClaw/Multiplayer/RemoteMotion.h"
#include <cassert>
#include <cmath>
int main() {
    Multiplayer::RemoteMotion motion;
    double x,y;
    motion.Push(100,200,1000); motion.Position(1000,x,y);
    assert(x==100 && y==200);
    motion.Push(108,200,1016); motion.Position(1024,x,y);
    assert(x>100 && x<120);
    const double first=x;
    motion.Position(1032,x,y); assert(x>first);
    // A dropped connection must not send the player flying across the map.
    motion.Position(5000,x,y); assert(x<=125.001);
    // Teleports, level changes and respawns snap instead of crossing the world.
    motion.Push(1000,300,5016); motion.Position(5016,x,y);
    assert(x==1000 && y==300);
    motion.Push(1005,300,5032); motion.Position(5040,x,y);
    assert(x>1000);
    motion.Push(10,20,5050,true); motion.Position(5050,x,y);
    assert(x==10 && y==20);
    // Timer wraparound preserves a short prediction interval.
    Multiplayer::RemoteMotion wrapped;
    wrapped.Push(0,0,0xfffffff0u); wrapped.Push(8,0,0);
    wrapped.Position(8,x,y); assert(std::isfinite(x) && x>=0 && x<=12);
}
