#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Animation/SkeletalMeshActor.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/WorldSettings.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Misc/AutomationTest.h"

namespace NLStagingQueueTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    struct FWorld
    {
        UWorld* World = nullptr;
        const uint64 SavedFrameCounter = GFrameCounter;
        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinQueue_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            AActor* Floor = World->SpawnActor<AActor>();
            UBoxComponent* Surface = NewObject<UBoxComponent>(Floor);
            Floor->SetRootComponent(Surface);
            Floor->AddInstanceComponent(Surface);
            Surface->SetBoxExtent(FVector(400, 800, 10));
            Surface->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Surface->SetCollisionResponseToAllChannels(ECR_Block);
            Surface->RegisterComponent();
            Floor->SetActorLocation(FVector(1000, 500, -10));
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrameCounter;
        }
        void Step(float Seconds = .1f)
        {
            ++GFrameCounter;
            World->Tick(LEVELTICK_All, Seconds);
        }
        ANLEncounterController* AddEncounter(bool bStaging, bool bSinglePoint = false)
        {
            ANLEncounterController* Encounter = World->SpawnActorDeferred<ANLEncounterController>(
                ANLEncounterController::StaticClass(), FTransform::Identity, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Encounter) return nullptr;
            Encounter->bShowStagingQueue = bStaging;
            Encounter->CorpseHoldSeconds = 0;
            UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(Encounter);
            Wave->WaveId = TEXT("QueueWave");
            Wave->MaxAlive = 2;
            Wave->SpawnIntervalSeconds = 10;
            Wave->MaxSpawnRetries = 0;
            FNLWaveSpawnEntry Entry;
            Entry.EntryId = TEXT("Disciples");
            Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
            Entry.Count = 6;
            for (int32 Index = 0; Index < (bSinglePoint ? 1 : 6); ++Index)
            {
                FNLWaveSpawnPoint Point;
                Point.SpawnPointId = FName(*FString::Printf(TEXT("Entry%d"), Index));
                Point.SpawnTransform.SetLocation(FVector(1000, Index * 200, 100));
                Encounter->SpawnPoints.Add(Point);
                Entry.SpawnPointIds.Add(Point.SpawnPointId);
            }
            Wave->SpawnEntries.Add(Entry);
            Encounter->Waves.Add(Wave);
            Encounter->FinishSpawning(FTransform::Identity);
            Encounter->StartEncounter();
            return Encounter;
        }
        TArray<ASkeletalMeshActor*> Displays(ANLEncounterController* Owner) const
        {
            TArray<ASkeletalMeshActor*> Result;
            for (TActorIterator<ASkeletalMeshActor> It(World); It; ++It)
                if (It->GetOwner() == Owner && !It->IsActorBeingDestroyed()
                    && It->ActorHasTag(TEXT("NL_StagedEnemyPreview"))) Result.Add(*It);
            return Result;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLStagingQueueLifecycleTest,
    "Nilin.Encounter.StagingQueue.NoncombatEntryPauseStopAndRetry", NLStagingQueueTests::Flags)

bool FNLStagingQueueLifecycleTest::RunTest(const FString& Parameters)
{
    using namespace NLStagingQueueTests;
    FWorld Scope;
    if (!TestNotNull(TEXT("Query-enabled isolated world"), Scope.World)) return false;
    ANLEncounterController* Encounter = Scope.AddEncounter(true);
    if (!TestNotNull(TEXT("Opt-in queue encounter"), Encounter)) return false;
    const int32 Seed = Encounter->GetCurrentRandomSeed();
    Scope.Step();
    TestEqual(TEXT("Only the authored first turn creates a combat enemy"), Encounter->GetSpawnedCount(), 1);
    TestEqual(TEXT("One living fighter"), Encounter->GetAliveCount(), 1);
    TestEqual(TEXT("Four pending disciples are visible"), Encounter->GetStagingPreviewCount(), 4);
    TestEqual(TEXT("Presentation does not consume composition RNG"), Encounter->GetCurrentRandomSeed(), Seed);
    const auto Displays = Scope.Displays(Encounter);
    TestEqual(TEXT("Public display count matches the actual transient actors"), Displays.Num(), 4);
    TSet<FName> Points;
    for (ASkeletalMeshActor* Display : Displays)
    {
        TestFalse(TEXT("Staged actors cannot collide"), Display->GetActorEnableCollision());
        TestNull(TEXT("Staging does not own a combat identity"), Display->FindComponentByClass<UNLCombatIdentityComponent>());
        TestNull(TEXT("Staging does not own health or death delegates"), Display->FindComponentByClass<UNLCombatVitalsComponent>());
        TestFalse(TEXT("Display cannot receive damage"), Display->CanBeDamaged());
        for (FName Tag : Display->Tags) if (Tag.ToString().StartsWith(TEXT("NL_StagedPoint_"))) Points.Add(Tag);
    }
    TestEqual(TEXT("No two staged disciples share an entrance"), Points.Num(), Displays.Num());
    Encounter->SetEncounterPaused(true);
    for (ASkeletalMeshActor* Display : Displays)
        TestTrue(TEXT("Controller-only pause freezes the pose"), Display->GetSkeletalMeshComponent()->bPauseAnims);
    Scope.Step(1);
    TestEqual(TEXT("Pause cannot add fighters"), Encounter->GetSpawnedCount(), 1);
    TestEqual(TEXT("Pause retains the queue"), Encounter->GetStagingPreviewCount(), 4);
    Encounter->SetEncounterPaused(false);
    // This fixture has no navigation. Isolate the already-spawned fighter's AI
    // while exercising the real encounter clock, spawn clearance and display pool.
    for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It)
        if (Encounter->OwnsEnemy(*It)) It->GetEnemyBrain()->SetComponentTickEnabled(false);
    // UWorld clamps a single oversized frame through AWorldSettings::FixupDeltaSeconds.
    // Advance real game time in ordinary frames instead of treating Tick(10.1) as ten seconds.
    const double ResumeTime = Scope.World->GetTimeSeconds();
    for (int32 Frame = 0; Frame < 110; ++Frame) Scope.Step(.1f);
    TestTrue(TEXT("The authored ten-second interval actually elapsed"), Scope.World->GetTimeSeconds() - ResumeTime >= 10.0);
    TestEqual(TEXT("The next turn creates exactly one more fighter"), Encounter->GetSpawnedCount(), 2);
    TestEqual(TEXT("Two fighters respect MaxAlive independently of the four displays"), Encounter->GetAliveCount(), 2);
    TestEqual(TEXT("Backfill keeps four remaining queued disciples"), Encounter->GetStagingPreviewCount(), 4);
    for (ASkeletalMeshActor* Display : Scope.Displays(Encounter))
        TestFalse(TEXT("The departed ordinal cannot remain as a display"), Display->ActorHasTag(TEXT("NL_StagedOrdinal_1")));
    Encounter->StopSpawningForObjective();
    TestEqual(TEXT("Objective completion removes every pending display immediately"), Encounter->GetStagingPreviewCount(), 0);
    TestEqual(TEXT("Objective stop leaves actual fighters alive"), Encounter->GetAliveCount(), 2);
    Encounter->CancelEncounter();
    Encounter->ResetEncounterForRetry(20261012, true);
    Scope.Step();
    TestEqual(TEXT("Retry starts a clean combat plan"), Encounter->GetSpawnedCount(), 1);
    TestEqual(TEXT("Retry recreates one bounded display pool"), Encounter->GetStagingPreviewCount(), 4);
    TestEqual(TEXT("Retry has no orphaned displays"), Scope.Displays(Encounter).Num(), 4);
    Encounter->CancelEncounter();
    TestEqual(TEXT("Cancel removes the pool"), Scope.Displays(Encounter).Num(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLStagingQueueBoundsTest,
    "Nilin.Encounter.StagingQueue.AuthoredPointsAndOptIn", NLStagingQueueTests::Flags)

bool FNLStagingQueueBoundsTest::RunTest(const FString& Parameters)
{
    using namespace NLStagingQueueTests;
    FWorld Scope;
    if (!TestNotNull(TEXT("Query-enabled isolated world"), Scope.World)) return false;
    ANLEncounterController* Encounter = Scope.AddEncounter(true, true);
    if (!TestNotNull(TEXT("Single authored rock entry"), Encounter)) return false;
    Scope.Step();
    TestEqual(TEXT("A live occupant prevents a staged mesh at the same entry"), Encounter->GetStagingPreviewCount(), 0);
    TestEqual(TEXT("No off-rock queue positions are invented"), Scope.Displays(Encounter).Num(), 0);
    Encounter->CancelEncounter();
    Encounter->bShowStagingQueue = false;
    Encounter->ResetEncounterForRetry(20261012, true);
    Scope.Step();
    TestEqual(TEXT("Legacy encounter stays opt-out"), Encounter->GetStagingPreviewCount(), 0);
    TestEqual(TEXT("Presentation setting does not change the planned six enemies"), Encounter->GetPlannedCount(), 6);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLStagingQueuePlayerApproachTest,
    "Nilin.Encounter.StagingQueue.PlayerApproachPreservesDisplayedDisciple", NLStagingQueueTests::Flags)

bool FNLStagingQueuePlayerApproachTest::RunTest(const FString& Parameters)
{
    using namespace NLStagingQueueTests;
    FWorld Scope;
    if (!TestNotNull(TEXT("Query-enabled world"), Scope.World)) return false;
    APawn* Player = Scope.World->SpawnActor<APawn>();
    USceneComponent* Root = NewObject<USceneComponent>(Player);
    Player->SetRootComponent(Root);
    Player->AddInstanceComponent(Root);
    Root->RegisterComponent();
    Player->SetActorLocation(FVector(-1000, -1000, 100));
    APlayerController* Controller = Scope.World->SpawnActor<APlayerController>();
    Controller->Possess(Player);
    Player->SetPlayerState(Scope.World->SpawnActor<APlayerState>());
    if (!TestTrue(TEXT("Real player-controller clearance is active"), Player->IsPlayerControlled())) return false;
    ANLEncounterController* Encounter = Scope.AddEncounter(true);
    if (!TestNotNull(TEXT("Queue encounter"), Encounter)) return false;
    Encounter->SetInstigator(Player);
    Scope.Step();
    TWeakObjectPtr<ANLEnemyCharacter> FirstEnemy;
    for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It)
        if (Encounter->OwnsEnemy(*It))
        {
            FirstEnemy = *It;
            It->GetEnemyBrain()->SetComponentTickEnabled(false);
        }
    ASkeletalMeshActor* DisplayedDisciple = nullptr;
    for (ASkeletalMeshActor* Display : Scope.Displays(Encounter))
        if (Display->ActorHasTag(TEXT("NL_StagedOrdinal_1"))) DisplayedDisciple = Display;
    if (!TestNotNull(TEXT("Next combat ordinal is visibly waiting"), DisplayedDisciple)) return false;
    const FVector OriginalDisplayLocation = DisplayedDisciple->GetActorLocation();
    FVector ExpectedSpawnLocation = FVector::ZeroVector;
    for (const FNLWaveSpawnPoint& Point : Encounter->SpawnPoints)
        if (DisplayedDisciple->ActorHasTag(FName(*FString::Printf(TEXT("NL_StagedPoint_%s"), *Point.SpawnPointId.ToString()))))
            ExpectedSpawnLocation = Point.SpawnTransform.GetLocation();
    Player->SetActorLocation(ExpectedSpawnLocation);
    for (int32 Frame = 0; Frame < 120; ++Frame) Scope.Step(.1f);
    TestFalse(TEXT("Approaching never destroys the displayed disciple"), DisplayedDisciple->IsActorBeingDestroyed());
    TestEqual(TEXT("Approaching never teleports the waiting disciple"), DisplayedDisciple->GetActorLocation(), OriginalDisplayLocation);
    TestEqual(TEXT("Player clearance defers the real combat handoff"), Encounter->GetSpawnedCount(), 1);
    TestEqual(TEXT("Safe proximity waiting does not consume failed-spawn retries"), Encounter->GetFailedSpawnCount(), 0);
    TestEqual(TEXT("Pending presentation pool remains visible"), Encounter->GetStagingPreviewCount(), 4);
    Player->SetActorLocation(FVector(-1000, -1000, 100));
    for (int32 Frame = 0; Frame < 5; ++Frame) Scope.Step(.1f);
    TestEqual(TEXT("Clearing the displayed entrance resumes the real spawn"), Encounter->GetSpawnedCount(), 2);
    TestTrue(TEXT("Only a successful real handoff retires the old display"), DisplayedDisciple->IsActorBeingDestroyed());
    ANLEnemyCharacter* HandedOffEnemy = nullptr;
    for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It)
        if (Encounter->OwnsEnemy(*It) && *It != FirstEnemy.Get()) HandedOffEnemy = *It;
    if (TestNotNull(TEXT("Actual combat replacement"), HandedOffEnemy))
        TestTrue(TEXT("Actual enemy keeps the displayed entrance instead of appearing elsewhere"),
            FVector::Dist2D(HandedOffEnemy->GetActorLocation(), ExpectedSpawnLocation) < 1.0f);
    return true;
}

#endif
