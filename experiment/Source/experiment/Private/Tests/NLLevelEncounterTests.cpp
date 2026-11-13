#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"

namespace NLLevelEncounterTests
{
    constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    /** Transient world for testing authored encounter stages without loading a map. */
    struct FScopedWorld
    {
        UWorld* World = nullptr;
        const uint64 SavedFrameCounter = GFrameCounter;

        FScopedWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            const FName Name(*FString::Printf(TEXT("NilinLevelEncounterTest_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
        }

        ~FScopedWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrameCounter;
        }

        APawn* AddPawn(ENLCombatFaction Faction, FVector Location = FVector::ZeroVector)
        {
            if (!World) return nullptr;
            APawn* Pawn = World->SpawnActor<APawn>();
            if (!Pawn) return nullptr;
            USceneComponent* Root = NewObject<USceneComponent>(Pawn);
            Pawn->SetRootComponent(Root);
            Pawn->AddInstanceComponent(Root);
            Root->RegisterComponent();
            Pawn->SetActorLocation(Location);
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Pawn);
            Identity->Faction = Faction;
            Pawn->AddInstanceComponent(Identity);
            Identity->RegisterComponent();
            Identity->EnsureRuntimeId();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Pawn);
            Pawn->AddInstanceComponent(Vitals);
            Vitals->RegisterComponent();
            Vitals->ResetVitals();
            return Pawn;
        }

        FNLLevelEncounterStage MakeStage(FName StageId, FName Required = NAME_None)
        {
            FNLLevelEncounterStage Stage;
            Stage.StageId = StageId;
            Stage.RequiredStageId = Required;
            Stage.TriggerExtent = FVector(100.0);
            Stage.EntryTransform.SetLocation(FVector(35.0, 20.0, 100.0));
            Stage.WarningSeconds = 20.0f;
            FNLWaveSpawnPoint Point;
            Point.SpawnPointId = TEXT("EntryPoint");
            Point.SpawnTransform.SetLocation(FVector(200.0, 0.0, 100.0));
            Stage.SpawnPoints.Add(Point);
            UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(World);
            Wave->WaveId = TEXT("Wave1");
            FNLWaveSpawnEntry Entry;
            Entry.EntryId = TEXT("Enemy1");
            Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
            Entry.Count = 1;
            Entry.SpawnPointIds.Add(Point.SpawnPointId);
            Wave->SpawnEntries.Add(Entry);
            Stage.Waves.Add(Wave);
            return Stage;
        }

        ANLLevelEncounterDirector* AddDirector(const TArray<FNLLevelEncounterStage>& Stages)
        {
            if (!World) return nullptr;
            ANLLevelEncounterDirector* Director = World->SpawnActorDeferred<ANLLevelEncounterDirector>(
                ANLLevelEncounterDirector::StaticClass(), FTransform::Identity, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Director) return nullptr;
            Director->Stages = Stages;
            Director->FinishSpawning(FTransform::Identity);
            return Director;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelEncounterEntryAndRetryTest,
    "Nilin.LevelEncounter.EntryDeathAndRetry", NLLevelEncounterTests::TestFlags)

bool FNLLevelEncounterEntryAndRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("Isolated test world"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player);
    APawn* Enemy = Scope.AddPawn(ENLCombatFaction::Enemy);
    APawn* Outside = Scope.AddPawn(ENLCombatFaction::Player, FVector(1000.0, 0.0, 0.0));
    const TArray<FNLLevelEncounterStage> Stages = {
        Scope.MakeStage(TEXT("A")), Scope.MakeStage(TEXT("B"), TEXT("A")), Scope.MakeStage(TEXT("Independent")) };
    ANLLevelEncounterDirector* Director = Scope.AddDirector(Stages);
    if (!TestNotNull(TEXT("Director"), Director) || !TestNotNull(TEXT("Player"), Player)
        || !TestNotNull(TEXT("Enemy pawn"), Enemy) || !TestNotNull(TEXT("Outside player"), Outside)) return false;

    TestEqual(TEXT("All authored regions are available to HUD"), Director->GetStageCount(), 3);
    TestEqual(TEXT("Required preceding stage starts locked"), Director->GetStageStatus(TEXT("B")), ENLLevelStageState::Locked);
    TestFalse(TEXT("A dependency cannot be bypassed by walking into B"), Director->TryActivateStage(TEXT("B"), Player));
    TestFalse(TEXT("Enemy-faction pawn cannot activate a region"), Director->TryActivateStage(TEXT("A"), Enemy));
    TestFalse(TEXT("Player outside the trigger cannot activate it"), Director->TryActivateStage(TEXT("A"), Outside));
    TestTrue(TEXT("Living player inside the trigger starts the warning"), Director->TryActivateStage(TEXT("A"), Player));
    TestEqual(TEXT("Warning does not count as a cleared stage"), Director->GetCompletedStageCount(), 0);
    TestEqual(TEXT("Entry triggers pre-combat warning"), Director->GetStageStatus(TEXT("A")), ENLLevelStageState::Warning);
    TestTrue(TEXT("Warning time is exposed to HUD"), Director->GetWarningRemaining() > 19.0f);
    TestNull(TEXT("No combat enemies/controller are spawned during warning"), Director->GetActiveEncounter());
    TestFalse(TEXT("Even an independent region cannot overlap the active warning"), Director->TryActivateStage(TEXT("Independent"), Player));
    TestFalse(TEXT("Repeated trigger cannot restart an active stage"), Director->TryActivateStage(TEXT("A"), Player));
    TestEqual(TEXT("Retry uses the authored safe capsule origin"), Director->GetRetryTransform().GetLocation(), FVector(35.0, 20.0, 100.0));

    UNLCombatVitalsComponent* Vitals = Player->FindComponentByClass<UNLCombatVitalsComponent>();
    if (!TestNotNull(TEXT("Player vitals"), Vitals)) return false;
    Vitals->ApplyCombatDamage(200.0f);
    TestEqual(TEXT("Death immediately fails the stage during warning"), Director->GetStageStatus(TEXT("A")), ENLLevelStageState::Failed);
    TestEqual(TEXT("Death never advances progress"), Director->GetCompletedStageCount(), 0);
    TestEqual(TEXT("Death does not unlock the next region"), Director->GetStageStatus(TEXT("B")), ENLLevelStageState::Locked);
    TestEqual(TEXT("Death has an explicit failure reason"), Director->GetFailureReason(), FName(TEXT("PlayerDied")));
    TestFalse(TEXT("A dead player cannot retry"), Director->RetryActiveStage());
    TestFalse(TEXT("Failed stage blocks bypass into another encounter"), Director->TryActivateStage(TEXT("Independent"), Outside));
    Vitals->ResetVitals();
    TestTrue(TEXT("After respawn, retry starts the same stage"), Director->RetryActiveStage());
    TestEqual(TEXT("Retry preserves stage identity"), Director->GetActiveStageId(), FName(TEXT("A")));
    TestEqual(TEXT("Retry starts a new warning"), Director->GetStageStatus(TEXT("A")), ENLLevelStageState::Warning);
    TestTrue(TEXT("Retry clears the old failure reason"), Director->GetFailureReason().IsNone());
    TestEqual(TEXT("Retry does not grant completion"), Director->GetCompletedStageCount(), 0);
    TestEqual(TEXT("Dependent stage remains locked after retry"), Director->GetStageStatus(TEXT("B")), ENLLevelStageState::Locked);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelEncounterSpawnWaitsForPlayerTest,
    "Nilin.LevelEncounter.SpawnWaitsForPlayerToClearPoint", NLLevelEncounterTests::TestFlags)

bool FNLLevelEncounterSpawnWaitsForPlayerTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("Isolated test world"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player);
    APlayerController* Controller = Scope.World->SpawnActor<APlayerController>();
    if (!TestNotNull(TEXT("Player pawn"), Player) || !TestNotNull(TEXT("Player controller"), Controller)) return false;
    Controller->Possess(Player);
    // This isolated world has no GameMode to provision the controller's PlayerState.
    Player->SetPlayerState(Scope.World->SpawnActor<APlayerState>());
    if (!TestTrue(TEXT("Pawn is controlled by a player"), Player->IsPlayerControlled())) return false;

    FNLLevelEncounterStage Stage = Scope.MakeStage(TEXT("A"));
    Stage.WarningSeconds = 0.01f;
    Stage.Waves[0]->MaxSpawnRetries = 0;
    ANLLevelEncounterDirector* Director = Scope.AddDirector({ Stage });
    if (!TestNotNull(TEXT("Director"), Director)) return false;
    if (!TestTrue(TEXT("Player activates the stage"), Director->TryActivateStage(Stage.StageId, Player))) return false;

    for (int32 Frame = 0; Frame < 6; ++Frame)
    {
        ++GFrameCounter;
        Scope.World->Tick(LEVELTICK_All, 0.1f);
    }
    ANLEncounterController* Encounter = Director->GetActiveEncounter();
    if (!TestNotNull(TEXT("Encounter starts after the warning"), Encounter)) return false;
    TestEqual(TEXT("No enemy spawns at the nearby point"), Encounter->GetSpawnedCount(), 0);
    TestEqual(TEXT("Player proximity does not spend the spawn retry budget"), Encounter->GetFailedSpawnCount(), 0);
    TestEqual(TEXT("Proximity keeps the stage active"), Director->GetStageStatus(Stage.StageId), ENLLevelStageState::Active);

    Player->SetActorLocation(FVector(-1000.0, 0.0, 0.0));
    for (int32 Frame = 0; Frame < 4 && Encounter->GetSpawnedCount() == 0; ++Frame)
    {
        ++GFrameCounter;
        Scope.World->Tick(LEVELTICK_All, 0.1f);
    }
    TestEqual(TEXT("The pending enemy spawns after the point clears"), Encounter->GetSpawnedCount(), 1);
    TestEqual(TEXT("The spawn completed without a failed attempt"), Encounter->GetFailedSpawnCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelEncounterInvalidConfigurationTest,
    "Nilin.LevelEncounter.RejectCyclesAndAmbiguousMasterRewards", NLLevelEncounterTests::TestFlags)

bool FNLLevelEncounterInvalidConfigurationTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("Isolated test world"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player);
    AddExpectedError(TEXT("configuration rejected: CyclicStageDependency"), EAutomationExpectedErrorFlags::Contains, 1);
    ANLLevelEncounterDirector* Cycle = Scope.AddDirector({ Scope.MakeStage(TEXT("A"), TEXT("B")), Scope.MakeStage(TEXT("B"), TEXT("A")) });
    if (!TestNotNull(TEXT("Cycle director remains inspectable"), Cycle)) return false;
    TestFalse(TEXT("Dependency cycle never activates combat"), Cycle->TryActivateStage(TEXT("A"), Player));
    TestEqual(TEXT("Cycle has a useful configuration failure"), Cycle->GetFailureReason(), FName(TEXT("CyclicStageDependency")));

    FNLLevelEncounterStage Master = Scope.MakeStage(TEXT("GM01"));
    Master.MasterId = TEXT("GM01");
    Master.Waves[0]->SpawnEntries[0].Count = 2;
    AddExpectedError(TEXT("configuration rejected: MasterFinalWaveMustPlanOneEnemy"), EAutomationExpectedErrorFlags::Contains, 1);
    ANLLevelEncounterDirector* Ambiguous = Scope.AddDirector({ Master });
    if (!TestNotNull(TEXT("Invalid master director"), Ambiguous)) return false;
    TestFalse(TEXT("Master reward cannot be attached to an arbitrary first kill of a group"), Ambiguous->TryActivateStage(TEXT("GM01"), Player));
    TestEqual(TEXT("Invalid master composition is diagnosed"), Ambiguous->GetFailureReason(), FName(TEXT("MasterFinalWaveMustPlanOneEnemy")));
    TestEqual(TEXT("Rejected configuration cannot advance progress"), Ambiguous->GetCompletedStageCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelEncounterMasterRewardOrderingTest,
    "Nilin.LevelEncounter.DisciplesBeforeMasterReward", NLLevelEncounterTests::TestFlags)

bool FNLLevelEncounterMasterRewardOrderingTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("Isolated test world"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player);
    FNLLevelEncounterStage Stage = Scope.MakeStage(TEXT("GM02"));
    Stage.DisplayName = FText::FromString(TEXT("Talisman Grandmaster"));
    Stage.MasterId = TEXT("GM02");
    Stage.Waves[0]->SpawnEntries[0].Count = 2;
    FNLLevelEncounterStage MasterWaveSource = Scope.MakeStage(TEXT("MasterWaveSource"));
    MasterWaveSource.Waves[0]->WaveId = TEXT("MasterFinalWave");
    Stage.Waves.Add(MasterWaveSource.Waves[0]);
    ANLLevelEncounterDirector* Director = Scope.AddDirector({ Stage });
    if (!TestNotNull(TEXT("Two disciples then one master director"), Director)) return false;
    TestTrue(TEXT("Earlier disciples followed by one final master are a valid configuration"), Director->GetFailureReason().IsNone());
    TestTrue(TEXT("Mixed master stage can enter its warning normally"), Director->TryActivateStage(TEXT("GM02"), Player));
    FNLLevelEncounterStage Snapshot;
    TestTrue(TEXT("Authored master stage remains queryable"), Director->GetStageDefinition(TEXT("GM02"), Snapshot));
    TestEqual(TEXT("Display name survives runtime snapshot"), Snapshot.DisplayName.ToString(), Stage.DisplayName.ToString());

    TestFalse(TEXT("First disciple death cannot emit master reward"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(0, 3, 0, 2));
    TestFalse(TEXT("Second disciple death cannot emit master reward"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(1, 3, 0, 2));
    TestFalse(TEXT("Final ordinal claimed in an earlier wave is rejected"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(2, 3, 0, 2));
    TestFalse(TEXT("Earlier disciple ordinal claimed in final wave is rejected"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(1, 3, 1, 2));
    TestTrue(TEXT("The final master defeat is eligible for first-kill reward"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(2, 3, 1, 2));
    TestFalse(TEXT("Uninitialized plan cannot emit a reward"),
        ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(INDEX_NONE, 0, INDEX_NONE, 0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelCombatBoundaryTest,
    "Nilin.LevelEncounter.BoundaryBlocksEscapeAndReleasesOnTerminalTransitions", NLLevelEncounterTests::TestFlags)

bool FNLLevelCombatBoundaryTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("Physics-query enabled world"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player, FVector(95, 0, 100));
    FNLLevelEncounterStage Stage = Scope.MakeStage(TEXT("Boundary"));
    Stage.WarningSeconds = .01f;
    ANLLevelEncounterDirector* Director = Scope.AddDirector({ Stage });
    if (!TestNotNull(TEXT("Boundary director"), Director) || !TestNotNull(TEXT("Player"), Player)) return false;
    const auto SweepOut = [&](const FVector& Direction, AActor*& HitActor)
    {
        FCollisionQueryParams Query(SCENE_QUERY_STAT(NLCombatBoundaryTest), false);
        Query.AddIgnoredActor(Player);
        for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It) Query.AddIgnoredActor(*It);
        FHitResult Hit;
        const FVector Start = Player->GetActorLocation();
        const bool bHit = Scope.World->SweepSingleByChannel(Hit, Start, Start + Direction * 2000.0,
            FQuat::Identity, ECC_Pawn, FCollisionShape::MakeCapsule(30.0f, 88.0f), Query);
        HitActor = Hit.GetActor();
        return bHit;
    };
    AActor* HitActor = nullptr;
    TestFalse(TEXT("No perimeter before encounter entry"), SweepOut(FVector::ForwardVector, HitActor));
    if (!TestTrue(TEXT("Player near the trigger edge starts warning safely"), Director->TryActivateStage(Stage.StageId, Player))) return false;
    TestTrue(TEXT("Warning closes the combat perimeter"), Director->IsCombatBoundaryLocked());
    const FVector Delta = (Player->GetActorLocation() - Director->GetCombatBoundaryCenter()).GetAbs();
    TestTrue(TEXT("New perimeter leaves at least 160cm around the activation capsule"),
        Director->GetCombatBoundaryExtent().X - Delta.X >= 159.0 && Director->GetCombatBoundaryExtent().Y - Delta.Y >= 159.0);
    for (const FVector Direction : { FVector(1, 0, 0), FVector(-1, 0, 0), FVector(0, 1, 0), FVector(0, -1, 0) })
    {
        TestTrue(TEXT("A real pawn-sized capsule sweep cannot escape in any horizontal direction"), SweepOut(Direction, HitActor));
        TestEqual(TEXT("Collision comes from the combat perimeter"), HitActor, static_cast<AActor*>(Director));
    }
    Player->SetActorLocation(Director->GetCombatBoundaryCenter()
        + FVector(Director->GetCombatBoundaryExtent().X - 150.0, 0, 0));
    TestTrue(TEXT("Approaching the perimeter exposes the clear-enemies guidance"), Director->IsPlayerNearCombatBoundary());
    TestFalse(TEXT("Boundary guidance is not empty"), Director->GetCombatBoundaryHint().IsEmpty());
    UNLCombatVitalsComponent* Vitals = Player->FindComponentByClass<UNLCombatVitalsComponent>();
    Vitals->ApplyCombatDamage(200.0f);
    TestFalse(TEXT("Death releases the perimeter immediately"), Director->IsCombatBoundaryLocked());
    TestFalse(TEXT("Death really removes blocking query geometry"), SweepOut(FVector::ForwardVector, HitActor));
    Vitals->ResetVitals();
    Player->SetActorLocation(Stage.EntryTransform.GetLocation());
    if (!TestTrue(TEXT("Retry starts the same region"), Director->RetryActiveStage())) return false;
    TestTrue(TEXT("Retry creates a fresh perimeter"), Director->IsCombatBoundaryLocked());
    Player->SetActorLocation(FVector(-200, -200, 100));
    for (int32 Frame = 0; Frame < 6; ++Frame) { ++GFrameCounter; Scope.World->Tick(LEVELTICK_All, .1f); }
    ANLEncounterController* Encounter = Director->GetActiveEncounter();
    if (!TestNotNull(TEXT("Actual encounter after warning"), Encounter)) return false;
    ANLEnemyCharacter* Fighter = nullptr;
    for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It)
        if (Encounter->OwnsEnemy(*It)) { Fighter = *It; break; }
    if (!TestNotNull(TEXT("Real final fighter"), Fighter)) return false;
    Fighter->GetEnemyBrain()->SetComponentTickEnabled(false);
    Fighter->Vitals->ApplyCombatDamage(500.0f);
    for (int32 Frame = 0; Frame < 3; ++Frame) { ++GFrameCounter; Scope.World->Tick(LEVELTICK_All, .1f); }
    TestEqual(TEXT("Actual final defeat completes the stage"), Director->GetStageStatus(Stage.StageId), ENLLevelStageState::Completed);
    TestFalse(TEXT("Completion unlocks the route"), Director->IsCombatBoundaryLocked());
    TestFalse(TEXT("Completion releases actual capsule collision"), SweepOut(FVector::ForwardVector, HitActor));
    Director->Destroy();
    TestFalse(TEXT("Leaving the level/director cannot leave orphaned collision"), SweepOut(FVector::ForwardVector, HitActor));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelUnreachableEnemyRecoveryTest,
    "Nilin.LevelEncounter.UnreachableLivingEnemyFailsAndReleasesBoundary", NLLevelEncounterTests::TestFlags)

bool FNLLevelUnreachableEnemyRecoveryTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelEncounterTests;
    FScopedWorld Scope;
    if (!TestNotNull(TEXT("World without a NavMesh"), Scope.World)) return false;
    APawn* Player = Scope.AddPawn(ENLCombatFaction::Player, FVector(-600, 0, 100));
    APlayerController* Controller = Scope.World->SpawnActor<APlayerController>();
    if (!TestNotNull(TEXT("Player"), Player) || !TestNotNull(TEXT("Player controller"), Controller)) return false;
    Controller->Possess(Player);
    Player->SetPlayerState(Scope.World->SpawnActor<APlayerState>());
    FNLLevelEncounterStage Stage = Scope.MakeStage(TEXT("Unreachable"));
    Stage.TriggerExtent = FVector(1200, 1200, 300);
    Stage.EntryTransform.SetLocation(Player->GetActorLocation());
    Stage.SpawnPoints[0].SpawnTransform.SetLocation(FVector(600, 0, 100));
    Stage.WarningSeconds = .01f;
    ANLLevelEncounterDirector* Director = Scope.AddDirector({ Stage });
    if (!TestNotNull(TEXT("Director"), Director)
        || !TestTrue(TEXT("Player enters stage"), Director->TryActivateStage(Stage.StageId, Player))) return false;
    for (int32 Frame = 0; Frame < 6; ++Frame) { ++GFrameCounter; Scope.World->Tick(LEVELTICK_All, .1f); }
    ANLEncounterController* Encounter = Director->GetActiveEncounter();
    if (!TestNotNull(TEXT("Active encounter"), Encounter)) return false;
    ANLEnemyCharacter* Enemy = nullptr;
    for (TActorIterator<ANLEnemyCharacter> It(Scope.World); It; ++It)
        if (Encounter->OwnsEnemy(*It)) { Enemy = *It; break; }
    if (!TestNotNull(TEXT("Living remote fighter"), Enemy)) return false;
    Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
    UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain();
    Brain->NavigationRecoveryLimitSeconds = 1.0f;
    Brain->NavigationReadyTimeoutSeconds = .5f;
    TestTrue(TEXT("Combat perimeter is initially sealed"), Director->IsCombatBoundaryLocked());
    for (int32 Frame = 0; Frame < 50; ++Frame) { ++GFrameCounter; Scope.World->Tick(LEVELTICK_All, .1f); }
    TestTrue(TEXT("Real missing-navigation timer reaches its bounded recovery limit"), Brain->IsNavigationRecoveryExhausted());
    TestEqual(TEXT("Unreachable enemy produces a retryable failure"), Encounter->GetState(), ENLEncounterState::Failed);
    TestEqual(TEXT("Failure identifies navigation instead of a fake death"), Encounter->GetFailureReason(), FName(TEXT("NavigationUnreachable")));
    TestEqual(TEXT("Director also enters Failed"), Director->GetStageStatus(Stage.StageId), ENLLevelStageState::Failed);
    TestFalse(TEXT("Enemy remains visible"), Enemy->IsHidden());
    TestFalse(TEXT("Enemy remains alive"), Enemy->Vitals->IsDead());
    TestEqual(TEXT("No defeat or reward progress is manufactured"), Encounter->GetDefeatedCount(), 0);
    TestFalse(TEXT("Failure cannot permanently imprison the player"), Director->IsCombatBoundaryLocked());
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(NLUnreachableBoundaryTest), false);
    Query.AddIgnoredActor(Player);
    Query.AddIgnoredActor(Enemy);
    TestFalse(TEXT("A real capsule sweep can leave after bounded failure"), Scope.World->SweepSingleByChannel(Hit,
        Player->GetActorLocation(), Player->GetActorLocation() + FVector(4000, 0, 0), FQuat::Identity,
        ECC_Pawn, FCollisionShape::MakeCapsule(30.0f, 88.0f), Query));
    TestTrue(TEXT("Living player may retry the failed area"), Director->RetryActiveStage());
    TestTrue(TEXT("Retry receives a fresh, recoverable boundary"), Director->IsCombatBoundaryLocked());
    return true;
}

#endif
