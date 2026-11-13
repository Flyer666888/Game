#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Objective/NLRitualObjective.h"
#include <limits>

namespace NLLevelObjectiveTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

    /** Disposable native world. No maps, saved profiles, navigation or content assets are changed. */
    struct FWorld
    {
        UWorld* World = nullptr;
        APawn* Player = nullptr;
        ANLRitualObjective* Objective = nullptr;
        ANLLevelEncounterDirector* Director = nullptr;
        uint64 SavedFrameCounter = GFrameCounter;

        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinLevelObjective_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Player = AddPawn(ENLCombatFaction::Player);
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

        APawn* AddPawn(ENLCombatFaction Faction)
        {
            APawn* Pawn = World->SpawnActor<APawn>();
            if (!Pawn) return nullptr;
            USceneComponent* Root = NewObject<USceneComponent>(Pawn);
            Pawn->SetRootComponent(Root);
            Pawn->AddInstanceComponent(Root);
            Root->RegisterComponent();
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Pawn);
            Identity->Faction = Faction;
            Pawn->AddInstanceComponent(Identity);
            Identity->RegisterComponent();
            Identity->EnsureRuntimeId();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Pawn);
            Vitals->DamageProtectionSeconds = 0.0f;
            Pawn->AddInstanceComponent(Vitals);
            Vitals->RegisterComponent();
            Vitals->ResetVitals();
            return Pawn;
        }

        ANLRitualObjective* AddObjective(FName Id = TEXT("Objective.Stage.Test"))
        {
            ANLRitualObjective* Result = World->SpawnActorDeferred<ANLRitualObjective>(
                ANLRitualObjective::StaticClass(), FTransform(FVector(1000, 0, 0)), nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            Result->ObjectiveStableId = Id;
            Result->bStartActive = false;
            Result->EffectiveRescueSeconds = 1.0f;
            Result->FinishSpawning(FTransform(FVector(1000, 0, 0)));
            return Result;
        }

        FNLLevelEncounterStage Stage(FName Id, FName ObjectiveId = NAME_None, FName Required = NAME_None)
        {
            FNLLevelEncounterStage S;
            S.StageId = Id;
            S.ObjectiveStableId = ObjectiveId;
            S.RequiredStageId = Required;
            S.WarningSeconds = 0.0f;
            S.TriggerExtent = FVector(100);
            S.EntryTransform = FTransform(FVector(0, 0, 100));
            FNLWaveSpawnPoint Point;
            Point.SpawnPointId = TEXT("Spawn.Test");
            Point.SpawnTransform = FTransform(FVector(2000, 0, 100));
            S.SpawnPoints.Add(Point);
            UNLWaveDefinition* Wave = NewObject<UNLWaveDefinition>(World);
            Wave->WaveId = FName(*FString::Printf(TEXT("Wave.%s"), *Id.ToString()));
            FNLWaveSpawnEntry Entry;
            Entry.EntryId = TEXT("Enemy.Test");
            Entry.EnemyClass = ANLEnemyCharacter::StaticClass();
            Entry.Count = 2;
            Entry.SpawnPointIds.Add(Point.SpawnPointId);
            Wave->SpawnEntries.Add(Entry);
            S.Waves.Add(Wave);
            return S;
        }

        ANLLevelEncounterDirector* AddDirector(const TArray<FNLLevelEncounterStage>& Stages)
        {
            ANLLevelEncounterDirector* Result = World->SpawnActorDeferred<ANLLevelEncounterDirector>(
                ANLLevelEncounterDirector::StaticClass(), FTransform::Identity, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            Result->Stages = Stages;
            Result->FinishSpawning(FTransform::Identity);
            return Result;
        }

        bool Setup()
        {
            if (!World || !Player) return false;
            Objective = AddObjective();
            Director = AddDirector({ Stage(TEXT("Rescue"), TEXT("Objective.Stage.Test")),
                Stage(TEXT("After"), NAME_None, TEXT("Rescue")) });
            return Objective && Director && Director->TryActivateStage(TEXT("Rescue"), Player);
        }

        bool Start()
        {
            Director->Tick(0.0f); // Zero warning, then real encounter BeginPlay/plan/start; no enemy Tick needed.
            return Director->GetStageStatus(TEXT("Rescue")) == ENLLevelStageState::Active && Director->GetActiveEncounter();
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelObjectivePreflightTest,
    "Nilin.LevelEncounter.Objective.MissingDuplicateAndInvalidPreflightIsAtomic", NLLevelObjectiveTests::Flags)

bool FNLLevelObjectivePreflightTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelObjectiveTests;
    FWorld F;
    if (!TestNotNull(TEXT("World"), F.World) || !TestNotNull(TEXT("Player"), F.Player)) return false;
    F.Director = F.AddDirector({ F.Stage(TEXT("Rescue"), TEXT("Objective.Stage.Test")) });
    TestFalse(TEXT("Missing objective rejects entry"), F.Director->TryActivateStage(TEXT("Rescue"), F.Player));
    TestEqual(TEXT("Missing objective explains entry block"), F.Director->GetEntryBlockReason(), FName(TEXT("MissingStageObjective")));
    TestTrue(TEXT("Rejected entry has no active stage"), F.Director->GetActiveStageId().IsNone());
    TestNull(TEXT("Rejected entry creates no encounter"), F.Director->GetActiveEncounter());
    F.Objective = F.AddObjective();
    ANLRitualObjective* Duplicate = F.AddObjective();
    TestFalse(TEXT("Duplicate stable identity rejects entry"), F.Director->TryActivateStage(TEXT("Rescue"), F.Player));
    TestEqual(TEXT("Duplicate diagnosis"), F.Director->GetEntryBlockReason(), FName(TEXT("DuplicateStageObjective")));
    Duplicate->Destroy();
    FNLObjectiveSnapshot Bad = F.Objective->CaptureObjectiveSnapshot();
    const FName OriginalFailure = F.Objective->GetLastFailureReason();
    Bad.Integrity = std::numeric_limits<float>::quiet_NaN();
    FName Reason;
    TestFalse(TEXT("Nonfinite scalar rejected without mutation"), F.Objective->CanRestoreObjectiveSnapshot(Bad, Reason));
    TestEqual(TEXT("Pure preflight preserves resource"), F.Objective->GetIntegrity(), 100.0f);
    TestEqual(TEXT("Pure preflight preserves failure diagnostic"), F.Objective->GetLastFailureReason(), OriginalFailure);
    TestTrue(TEXT("One correct objective permits entry"), F.Director->TryActivateStage(TEXT("Rescue"), F.Player));
    F.Objective->ObjectiveStableId = TEXT("Objective.Wrong");
    TestFalse(TEXT("Wrong ID blocks retry preflight before respawn or wave cleanup"), F.Director->CanRetryActiveStage(Reason));
    TestEqual(TEXT("Preflight leaves warning intact"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Warning);
    TestEqual(TEXT("Preflight leaves player resources intact"), F.Player->FindComponentByClass<UNLCombatVitalsComponent>()->GetHealth(), 100.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelObjectiveRetryTest,
    "Nilin.LevelEncounter.Objective.EntryPauseFailureAndTenRetries", NLLevelObjectiveTests::Flags)

bool FNLLevelObjectiveRetryTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelObjectiveTests;
    FWorld F;
    if (!TestTrue(TEXT("Fixture enters objective warning"), F.Setup())) return false;
    F.Objective->Tick(10.0f);
    TestEqual(TEXT("Warning never advances rescue"), F.Objective->GetRescueProgress(), 0.0f);
    TestEqual(TEXT("Entry captures full integrity"), F.Director->GetRetryObjectiveSnapshot().Integrity, 100.0f);
    for (int32 Attempt = 0; Attempt < 10; ++Attempt)
    {
        if (!TestTrue(TEXT("Native director starts its encounter"), F.Start())) return false;
        ANLEncounterController* Encounter = F.Director->GetActiveEncounter();
        F.Objective->Tick(.25f);
        TestEqual(TEXT("Active objective advances"), F.Objective->GetRescueProgress(), 25.0f);
        Encounter->SetEncounterPaused(true);
        F.Objective->Tick(1.0f);
        TestEqual(TEXT("Encounter-local pause freezes objective"), F.Objective->GetRescueProgress(), 25.0f);
        Encounter->SetEncounterPaused(false);
        APawn* Source = F.AddPawn(ENLCombatFaction::Enemy);
        Source->SetOwner(Encounter);
        TestTrue(TEXT("A live source can interfere"), F.Objective->RegisterInterferenceSource(TEXT("Source.Test"), Source));
        UNLAttackDefinition* Attack = NewObject<UNLAttackDefinition>(F.World);
        Attack->StableId = TEXT("Attack.Test.Objective");
        ANLCombatProjectile* Shot = F.World->SpawnActor<ANLCombatProjectile>();
        TestTrue(TEXT("Real encounter-owned projectile initialized"), Shot->InitializeProjectile(Source, Attack, FVector::ForwardVector, 100.0f, 2.0f));
        // Direct integrity loss isolates the stage failure/retry contract; combat resolver policy has separate tests.
        F.Objective->Vitals->ApplyCombatDamage(100.0f);
        TestEqual(TEXT("Ritual failure immediately fails main stage"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Failed);
        TestEqual(TEXT("Failure never unlocks successor"), F.Director->GetStageStatus(TEXT("After")), ENLLevelStageState::Locked);
        TestTrue(TEXT("Failure removes the old owned projectile"), Shot->IsActorBeingDestroyed());
        TestTrue(TEXT("Failed stage can retry with validated entrance"), F.Director->RetryActiveStage());
        TestTrue(TEXT("Old encounter is destroyed"), Encounter->IsActorBeingDestroyed());
        TestEqual(TEXT("Retry restores entrance integrity"), F.Objective->GetIntegrity(), 100.0f);
        TestEqual(TEXT("Retry restores entrance progress"), F.Objective->GetRescueProgress(), 0.0f);
        TestEqual(TEXT("Retry clears old interference"), F.Objective->GetInterferenceSourceCount(), 0);
        TestEqual(TEXT("Retry clears old required threats"), F.Objective->GetRemainingThreatCount(), 0);
        TestFalse(TEXT("Retry has no ghost source-rebuild hold"), F.Objective->IsAwaitingSourceRebuild());
        TestEqual(TEXT("Retry grants no rescue"), F.Objective->GetCompletionEventCount(), 0);
        Source->Destroy();
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelObjectiveFlowTest,
    "Nilin.LevelEncounter.Objective.PendingStopsSpawnsAndWaitsForEnemiesAndShots", NLLevelObjectiveTests::Flags)

bool FNLLevelObjectiveFlowTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelObjectiveTests;
    FWorld F;
    if (!TestTrue(TEXT("Fixture ready"), F.Setup() && F.Start())) return false;
    ANLEncounterController* Encounter = F.Director->GetActiveEncounter();
    // A native owned enemy is registered explicitly to isolate objective gating from NavMesh generation.
    ANLEnemyCharacter* Enemy = F.World->SpawnActorDeferred<ANLEnemyCharacter>(ANLEnemyCharacter::StaticClass(),
        FTransform(FVector(3000, 0, 100)), Encounter, F.Player, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!TestNotNull(TEXT("Native threat"), Enemy)) return false;
    Enemy->FinishSpawning(FTransform(FVector(3000, 0, 100)));
    TestNotNull(TEXT("Native threat keeps its real automatically spawned controller"), Enemy->GetController());
    TestTrue(TEXT("Possession owns the pawn; Actor Owner is not its encounter membership"),
        Enemy->GetOwner() == Enemy->GetController() && Enemy->GetOwner() != Encounter);
    Enemy->SetCombatEnabled(false);
    ANLEncounterController::FOwnedEnemy Record;
    Record.Enemy = Enemy;
    Record.RuntimeId = Enemy->CombatIdentity->EnsureRuntimeId();
    Record.Generation = Encounter->EncounterGeneration;
    Record.WaveIndex = 0;
    Record.SpawnOrdinal = 0;
    Encounter->OwnedEnemies.Add(Record);
    TestTrue(TEXT("Encounter spawn record authoritatively owns the possessed enemy"), Encounter->OwnsEnemy(Enemy));
    UNLAttackDefinition* Attack = NewObject<UNLAttackDefinition>(F.World);
    Attack->StableId = TEXT("Attack.Test.ObjectiveFlow");
    ANLCombatProjectile* Shot = F.World->SpawnActor<ANLCombatProjectile>();
    if (!TestTrue(TEXT("Real hostile shot"), Shot->InitializeProjectile(Enemy, Attack, FVector::ForwardVector, 100.0f, 2.0f))) return false;
    // Keep the real projectile sweep away from fixture bodies; verify the encounter's
    // pause/cleanup ownership without changing the possessed pawn's Actor Owner.
    const FVector ShotStart(3000, 0, 400);
    Shot->SetActorLocation(ShotStart);
    ANLCombatProjectile::SetEncounterProjectilesPaused(Encounter, true);
    Shot->Tick(.2f);
    TestEqual(TEXT("Encounter pause reaches a shot from its possessed enemy"), Shot->GetActorLocation(), ShotStart);
    ANLCombatProjectile::SetEncounterProjectilesPaused(Encounter, false);
    Shot->Tick(.2f);
    TestTrue(TEXT("Encounter resume restores the real projectile sweep"),
        Shot->GetActorLocation().Equals(ShotStart + FVector(20, 0, 0), .01f) && !Shot->IsActorBeingDestroyed());
    F.Objective->Tick(1.0f);
    TestTrue(TEXT("100 percent is a candidate"), F.Objective->IsCompletionPending());
    TestTrue(TEXT("Candidate stops every remaining spawn"), Encounter->IsSpawningStoppedForObjective());
    TestFalse(TEXT("Unspawned enemy cannot escape stop gate"), Encounter->TrySpawnNext());
    TestEqual(TEXT("Pending registers live enemy and projectile independently"), F.Objective->GetRemainingThreatCount(), 2);
    ++GFrameCounter;
    F.Objective->Tick(.1f);
    TestEqual(TEXT("Live threats keep stage active"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Active);
    Enemy->Vitals->ApplyCombatDamage(1000.0f);
    F.Objective->Tick(.1f);
    TestEqual(TEXT("Caster death does not erase its flying shot"), F.Objective->GetRemainingThreatCount(), 1);
    TestFalse(TEXT("Flying shot still delays rescue"), F.Objective->IsRescueCompleted());
    ANLCombatProjectile::DestroyEncounterProjectiles(Encounter);
    TestTrue(TEXT("Encounter cleanup reaches the flying shot after caster death"), Shot->IsActorBeingDestroyed());
    ++GFrameCounter;
    F.Objective->Tick(.1f);
    TestEqual(TEXT("Cleared threats complete the objective stage"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Completed);
    TestEqual(TEXT("Success unlocks the actual dependent stage"), F.Director->GetStageStatus(TEXT("After")), ENLLevelStageState::Available);
    TestEqual(TEXT("Rescue is emitted once"), F.Objective->GetCompletionEventCount(), 1);
    for (int32 I = 0; I < 3; ++I) { ++GFrameCounter; F.Objective->Tick(1.0f); }
    TestEqual(TEXT("No repeat completion"), F.Objective->GetCompletionEventCount(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelObjectiveSameFrameTest,
    "Nilin.LevelEncounter.Objective.ZeroIntegrityWinsCompletionFrame", NLLevelObjectiveTests::Flags)

bool FNLLevelObjectiveSameFrameTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelObjectiveTests;
    for (bool bProgressFirst : { false, true })
    {
        FWorld F;
        if (!TestTrue(TEXT("Tie fixture ready"), F.Setup() && F.Start())) return false;
        if (bProgressFirst) F.Objective->Tick(1.0f);
        F.Objective->Vitals->ApplyCombatDamage(100.0f);
        if (!bProgressFirst) F.Objective->Tick(1.0f);
        ++GFrameCounter;
        F.Objective->Tick(.1f);
        TestEqual(TEXT("Both callback orders fail the stage"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Failed);
        TestEqual(TEXT("Both orders emit no rescue"), F.Objective->GetCompletionEventCount(), 0);
        TestEqual(TEXT("Both orders keep next stage locked"), F.Director->GetStageStatus(TEXT("After")), ENLLevelStageState::Locked);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLLevelObjectiveReentrantFailureTest,
    "Nilin.LevelEncounter.Objective.ReentrantFailureCommitsBeforeObjectiveNotification", NLLevelObjectiveTests::Flags)

bool FNLLevelObjectiveReentrantFailureTest::RunTest(const FString& Parameters)
{
    using namespace NLLevelObjectiveTests;
    FWorld F;
    if (!TestTrue(TEXT("Reentry fixture ready"), F.Setup() && F.Start())) return false;
    // Bind the existing, signature-compatible production failure callback to the objective's
    // synchronous change event. This deliberately calls FailActiveStage again while it pauses
    // the ritual; no test-only UCLASS or runtime bypass is required.
    FScriptDelegate ReenterFailure;
    ReenterFailure.BindUFunction(F.Director, FName(TEXT("HandleObjectiveFailed")));
    F.Objective->OnObjectiveChanged.Add(ReenterFailure);
    F.Director->FailActiveStage(TEXT("DeliberateReentrantFailure"));
    TestEqual(TEXT("Reentrant objective notification cannot recurse or change terminal state"),
        F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Failed);
    TestEqual(TEXT("Nested callback does not overwrite original failure cause"),
        F.Director->GetFailureReason(), FName(TEXT("DeliberateReentrantFailure")));
    TestEqual(TEXT("Reentrant failure does not unlock the next stage"),
        F.Director->GetStageStatus(TEXT("After")), ENLLevelStageState::Locked);
    TestEqual(TEXT("Reentrant notification grants no rescue"), F.Objective->GetCompletionEventCount(), 0);
    F.Objective->OnObjectiveChanged.Remove(ReenterFailure);
    TestTrue(TEXT("After unwinding, normal retry remains possible"), F.Director->RetryActiveStage());
    TestEqual(TEXT("Retry restores warning after reentry"), F.Director->GetStageStatus(TEXT("Rescue")), ENLLevelStageState::Warning);
    return true;
}

#endif
