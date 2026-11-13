#include "Player/NLVRGameMode.h"
#include "Player/NLVRPlayerCharacter.h"
#include "Player/NLCombatLabHUD.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

ANLVRGameMode::ANLVRGameMode()
{
    DefaultPawnClass = ANLVRPlayerCharacter::StaticClass();
    HUDClass = ANLCombatLabHUD::StaticClass();
}

void ANLVRGameMode::StartPlay()
{
    Super::StartPlay();
    const bool bSpectatorEntry = UGameplayStatics::ParseOption(OptionsString, TEXT("SpectatorOnly")) == TEXT("1");
    UE_LOG(LogTemp, Log, TEXT("VR scene entry: map=%s pawn=%s spectator=%s readyPreviews=%s"),
        *GetWorld()->GetMapName(), *GetNameSafe(UGameplayStatics::GetPlayerPawn(this, 0)),
        bSpectatorEntry ? TEXT("yes") : TEXT("no"), bShowReadyEnemyPreviews ? TEXT("yes") : TEXT("no"));
    if (bSpectatorEntry)
    {
        const FString Message = TEXT("SIMULATE / SPECTATOR: READY ENEMIES ARE DISPLAY ONLY. PLAY WITH Run_VR_Demo.cmd OR VR PREVIEW.");
        UE_LOG(LogTemp, Warning, TEXT("%s No controlled VR player was requested by this entry mode."), *Message);
        if (GEngine) GEngine->AddOnScreenDebugMessage(INDEX_NONE, 60.0f, FColor::Yellow, Message);
    }
}

void ANLVRGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    // Select before player login creates the HUD. Main-level feedback lives in
    // the VR pawn's spatial text; the laboratory canvas contains desktop key hints.
    for (TActorIterator<ANLLevelEncounterDirector> It(GetWorld()); It; ++It)
        if (!It->IsActorBeingDestroyed())
        {
            HUDClass = nullptr;
            break;
        }
    Super::InitGame(MapName, Options, ErrorMessage);
}
