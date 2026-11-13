#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "NLVRGameMode.generated.h"

/** Dedicated OpenXR lab; desktop maps retain their existing game mode. */
UCLASS()
class EXPERIMENT_API ANLVRGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ANLVRGameMode();
};
