#include "Player/NLVRGameMode.h"
#include "Player/NLVRPlayerCharacter.h"
#include "Player/NLCombatLabHUD.h"

ANLVRGameMode::ANLVRGameMode()
{
    DefaultPawnClass = ANLVRPlayerCharacter::StaticClass();
    HUDClass = ANLCombatLabHUD::StaticClass();
}
