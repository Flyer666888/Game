#if WITH_DEV_AUTOMATION_TESTS

#include "Objective/NLRitualObjective.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Save/NLCheckpointService.h"
#include <limits>

namespace NLRitualTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FBody
    {
        AActor* Actor = nullptr;
        UNLCombatIdentityComponent* Identity = nullptr;
        UNLCombatVitalsComponent* Vitals = nullptr;
        bool IsReady() const { return Actor && Identity && Vitals; }
    };

    /** Real objective, vitals and resolver in a disposable world; no project save files. */
    class FWorld
    {
    public:
        FWorld() : SavedFrameCounter(GFrameCounter)
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            const FName Name(*FString::Printf(TEXT("NilinRitualTest_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Resolver = World->GetSubsystem<UNLCombatResolverSubsystem>();
            Objective = World->SpawnActor<ANLRitualObjective>();
            if (Objective)
            {
                Objective->InitializeObjective(TEXT("Objective.Test.Ritual"));
                Objective->AllowedAttackDefinitionIds.Add(TEXT("Attack.Test.RitualHostile"));
            }
            Definition = NewObject<UNLAttackDefinition>(World);
            Definition->StableId = TEXT("Attack.Test.RitualHostile");
            Definition->Damage = 20.0f;
            Definition->bCanBeBlocked = false;
            Player = AddBody(ENLCombatFaction::Player);
            EnemyOne = AddBody(ENLCombatFaction::Enemy);
            EnemyTwo = AddBody(ENLCombatFaction::Enemy);
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                if (GEngine) GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrameCounter;
        }
        bool IsReady() const
        {
            return World && Resolver && Objective && Objective->HasActorBegunPlay() && Definition
                && Player.IsReady() && EnemyOne.IsReady() && EnemyTwo.IsReady();
        }
        FBody AddBody(ENLCombatFaction Faction)
        {
            FBody Body;
            Body.Actor = World->SpawnActor<AActor>();
            if (!Body.Actor) return Body;
            USceneComponent* Root = NewObject<USceneComponent>(Body.Actor);
            Body.Actor->SetRootComponent(Root);
            Body.Actor->AddInstanceComponent(Root);
            Root->RegisterComponent();
            Body.Identity = NewObject<UNLCombatIdentityComponent>(Body.Actor);
            Body.Identity->Faction = Faction;
            Body.Actor->AddInstanceComponent(Body.Identity);
            Body.Identity->RegisterComponent();
            Body.Identity->EnsureRuntimeId();
            Body.Vitals = NewObject<UNLCombatVitalsComponent>(Body.Actor);
            Body.Vitals->DamageProtectionSeconds = 0.0f;
            Body.Actor->AddInstanceComponent(Body.Vitals);
            Body.Vitals->RegisterComponent();
            Body.Vitals->ResetVitals();
            return Body;
        }
        void Tick(float Seconds, bool bAdvanceFrame = true)
        {
            // Small real game frames avoid depending on the engine's large-delta clamp.
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(Seconds / .1f));
            for (int32 I = 0; I < Steps; ++I)
            {
                const float Step = FMath::Max(0.0f, FMath::Min(.1f, Seconds - I * .1f));
                World->Tick(LEVELTICK_All, Step);
                if (bAdvanceFrame) ++GFrameCounter;
            }
        }
        FNLCombatContact Contact(const FBody& Source, AActor* Target) const
        {
            FNLCombatContact C;
            C.AttackInstanceId = FGuid::NewGuid();
            C.SourceRuntimeId = Source.Identity->EnsureRuntimeId();
            C.TargetRuntimeId = Target->FindComponentByClass<UNLCombatIdentityComponent>()->EnsureRuntimeId();
            C.ProjectileGeneration = INDEX_NONE;
            C.ContactTimeSeconds = World->GetTimeSeconds();
            C.HitPosition = Target->GetActorLocation();
            C.AttackDefinitionId = Definition->StableId;
            return C;
        }
        FNLCombatResult Hit(const FBody& Source, AActor* Target)
        { return Resolver->ResolveContact(Source.Actor, Target, Contact(Source, Target), Definition); }
        void Defeat(const FBody& Enemy)
        {
            const float PreviousDamage = Definition->Damage;
            Definition->Damage = 1000.0f;
            Hit(Player, Enemy.Actor);
            Definition->Damage = PreviousDamage;
        }
        UWorld* World = nullptr;
        ANLRitualObjective* Objective = nullptr;
        UNLCombatResolverSubsystem* Resolver = nullptr;
        UNLAttackDefinition* Definition = nullptr;
        FBody Player, EnemyOne, EnemyTwo;
    private:
        uint64 SavedFrameCounter;
    };
}

using namespace NLRitualTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualProgressSourcesTest,
    "Nilin.Objective.Ritual.ProgressAndTwoSources", NLRitualTests::Flags)
bool FNLRitualProgressSourcesTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Real objective and combat world begin play"), F.IsReady())) return false;
    F.Tick(24.0f);
    TestTrue(TEXT("GDD 240 effective seconds means 24 seconds earns 10 percent"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    TestTrue(TEXT("First caster registers its stable source"), F.Objective->RegisterInterferenceSource(TEXT("Caster.One"), F.EnemyOne.Actor));
    TestTrue(TEXT("Second caster registers independently"), F.Objective->RegisterInterferenceSource(TEXT("Caster.Two"), F.EnemyTwo.Actor));
    TestFalse(TEXT("Duplicate ID cannot multiply interference"), F.Objective->RegisterInterferenceSource(TEXT("Caster.One"), F.EnemyTwo.Actor));
    TestFalse(TEXT("One caster cannot multiply interference with fresh IDs"), F.Objective->RegisterInterferenceSource(TEXT("Caster.OtherAlias"), F.EnemyOne.Actor));
    F.Tick(60.0f);
    TestTrue(TEXT("Two live sources stop progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    F.Defeat(F.EnemyOne);
    TestEqual(TEXT("Resolver-driven caster death immediately removes only its source"), F.Objective->GetInterferenceSourceCount(), 1);
    F.Tick(24.0f);
    TestTrue(TEXT("One remaining source still stops progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    TestTrue(TEXT("Interrupt explicitly removes the surviving source"), F.Objective->UnregisterInterferenceSource(TEXT("Caster.Two")));
    F.Tick(24.0f);
    TestTrue(TEXT("Progress resumes without catch-up for interrupted time"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 20.0f, .001f));
    TestTrue(TEXT("Living caster can start a new interference"), F.Objective->RegisterInterferenceSource(TEXT("Caster.Two"), F.EnemyTwo.Actor));
    F.EnemyTwo.Actor->Destroy();
    TestEqual(TEXT("Leaving/destroying actor removes stale source immediately"), F.Objective->GetInterferenceSourceCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualResolverPolicyTest,
    "Nilin.Objective.Ritual.ResolverPolicyAndDedup", NLRitualTests::Flags)
bool FNLRitualResolverPolicyTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Real ritual and resolver begin play"), F.IsReady())) return false;
    TestTrue(TEXT("Player melee cannot harm rescue objective"), F.Hit(F.Player, F.Objective).Outcome == ENLCombatOutcome::Ignored);
    TestEqual(TEXT("Friendly skill/melee leaves full integrity"), F.Objective->GetIntegrity(), 100.0f);
    F.Definition->StableId = TEXT("Attack.Test.NotAuthoredForRitual");
    TestTrue(TEXT("Enemy attack must be explicitly allowed for the ritual"), F.Hit(F.EnemyOne, F.Objective).Outcome == ENLCombatOutcome::Ignored);
    F.Definition->StableId = TEXT("Attack.Test.RitualHostile");
    const FNLCombatContact C = F.Contact(F.EnemyOne, F.Objective);
    const FNLCombatResult Hit = F.Resolver->ResolveContact(F.EnemyOne.Actor, F.Objective, C, F.Definition);
    TestTrue(TEXT("Allowed hostile contact uses ritual damage result"), Hit.Outcome == ENLCombatOutcome::RitualDamaged);
    TestEqual(TEXT("Ritual damage has distinct feedback"), Hit.FeedbackTag, FName(TEXT("Combat.RitualDamaged")));
    TestEqual(TEXT("Allowed hit removes actual integrity"), F.Objective->GetIntegrity(), 80.0f);
    TestTrue(TEXT("Same attack/target is deduplicated"), F.Resolver->ResolveContact(F.EnemyOne.Actor, F.Objective, C, F.Definition).Outcome == ENLCombatOutcome::Ignored);
    TestEqual(TEXT("Duplicate cannot damage twice"), F.Objective->GetIntegrity(), 80.0f);
    TestTrue(TEXT("Distinct same-frame hostile hit is valid independently of player protection timer"), F.Hit(F.EnemyTwo, F.Objective).Outcome == ENLCombatOutcome::RitualDamaged);
    TestEqual(TEXT("Ritual owns its own unprotected integrity"), F.Objective->GetIntegrity(), 60.0f);
    F.Objective->SetCombatPaused(true);
    TestTrue(TEXT("Local encounter pause rejects ritual damage"), F.Hit(F.EnemyOne, F.Objective).Outcome == ENLCombatOutcome::Ignored);
    TestEqual(TEXT("Paused integrity is unchanged"), F.Objective->GetIntegrity(), 60.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualCompletionThreatsTest,
    "Nilin.Objective.Ritual.CompletionWaitsForRequiredThreats", NLRitualTests::Flags)
bool FNLRitualCompletionThreatsTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Fixture begins play"), F.IsReady())) return false;
    F.Objective->InitializeObjective(TEXT("Objective.Test.Ritual"), 100.0f, 1.0f);
    F.Objective->RegisterRemainingThreat(TEXT("Threat.One"), F.EnemyOne.Actor);
    F.Objective->RegisterRemainingThreat(TEXT("Threat.Two"), F.EnemyTwo.Actor);
    F.Tick(1.0f);
    TestTrue(TEXT("100 percent locks only a completion candidate"), F.Objective->IsCompletionPending());
    TestFalse(TEXT("Reaching full progress does not immediately rescue"), F.Objective->IsRescueCompleted());
    TestFalse(TEXT("Later interference cannot reopen a locked completion candidate"), F.Objective->RegisterInterferenceSource(TEXT("Late.Caster"), F.EnemyOne.Actor));
    F.Tick(.1f);
    TestEqual(TEXT("Required living threats delay final rescue"), F.Objective->GetCompletionEventCount(), 0);
    F.Defeat(F.EnemyOne);
    TestEqual(TEXT("First death clears only one required threat"), F.Objective->GetRemainingThreatCount(), 1);
    F.Defeat(F.EnemyTwo);
    F.Tick(.1f);
    TestTrue(TEXT("Clearing final valid threat completes rescue"), F.Objective->IsRescueCompleted());
    TestEqual(TEXT("Success event is emitted exactly once"), F.Objective->GetCompletionEventCount(), 1);
    for (int32 I = 0; I < 5; ++I) F.Tick(1.0f);
    TestEqual(TEXT("Later frames cannot repeat success"), F.Objective->GetCompletionEventCount(), 1);
    TestTrue(TEXT("Completed ritual rejects later damage"), F.Hit(F.EnemyOne, F.Objective).Outcome == ENLCombatOutcome::Ignored);
    TestEqual(TEXT("No failure follows a locked completion"), F.Objective->GetFailureEventCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualSameFramePriorityTest,
    "Nilin.Objective.Ritual.ZeroIntegrityWinsSameFrameBothOrders", NLRitualTests::Flags)
bool FNLRitualSameFramePriorityTest::RunTest(const FString& Parameters)
{
    for (const bool bProgressFirst : { false, true })
    {
        FWorld F;
        if (!TestTrue(TEXT("Tie fixture begins play"), F.IsReady())) return false;
        F.Objective->InitializeObjective(TEXT("Objective.Test.Ritual"), 100.0f, 1.0f);
        FNLObjectiveSnapshot Entrance = F.Objective->CaptureObjectiveSnapshot();
        Entrance.RescueProgress = 99.0f;
        TestTrue(TEXT("99-percent test entrance restores"), F.Objective->RestoreObjectiveSnapshot(Entrance));
        F.Objective->FinishSourceRebuild();
        F.Definition->Damage = 100.0f;
        if (bProgressFirst)
        {
            F.Tick(.02f, false);
            TestTrue(TEXT("Progress first is pending, not a same-frame success"), F.Objective->IsCompletionPending());
            F.Hit(F.EnemyOne, F.Objective);
        }
        else
        {
            F.Hit(F.EnemyOne, F.Objective);
            F.Tick(.02f, false);
        }
        ++GFrameCounter;
        F.Tick(.1f);
        TestTrue(TEXT("Zero integrity wins regardless of caller/tick order"), F.Objective->IsFailureLocked());
        TestEqual(TEXT("Tie produces one failure"), F.Objective->GetFailureEventCount(), 1);
        TestEqual(TEXT("Tie never produces a contradictory rescue"), F.Objective->GetCompletionEventCount(), 0);
        TestEqual(TEXT("Failure clears all interference"), F.Objective->GetInterferenceSourceCount(), 0);
        F.Tick(1.0f);
        TestEqual(TEXT("Failed objective cannot repeat its result"), F.Objective->GetFailureEventCount(), 1);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualPauseRetryTest,
    "Nilin.Objective.Ritual.GlobalLocalPauseAndRetryCleanup", NLRitualTests::Flags)
bool FNLRitualPauseRetryTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Pause fixture begins play"), F.IsReady())) return false;
    F.Tick(24.0f);
    F.Objective->SetCombatPaused(true);
    F.Tick(24.0f);
    TestTrue(TEXT("Local pause freezes progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    F.Objective->SetCombatPaused(false);
    F.Tick(24.0f);
    TestTrue(TEXT("Resume does not catch up paused wall time"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 20.0f, .001f));
    APlayerState* Pauser = F.World->SpawnActor<APlayerState>();
    F.World->GetWorldSettings()->SetPauserPlayerState(Pauser);
    TestTrue(TEXT("World reports actual game pause"), F.World->IsPaused());
    F.Tick(24.0f);
    TestTrue(TEXT("Global pause freezes progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 20.0f, .001f));
    TestTrue(TEXT("Paused resolver cannot harm ritual"), F.Hit(F.EnemyOne, F.Objective).Outcome == ENLCombatOutcome::Ignored);
    F.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
    F.Objective->RegisterInterferenceSource(TEXT("Caster.BeforeRetry"), F.EnemyOne.Actor);
    F.Objective->RegisterRemainingThreat(TEXT("Threat.BeforeRetry"), F.EnemyTwo.Actor);
    F.Objective->ResetForEncounter();
    TestEqual(TEXT("Retry clears every prior source"), F.Objective->GetInterferenceSourceCount(), 0);
    TestEqual(TEXT("Retry clears remaining threat references"), F.Objective->GetRemainingThreatCount(), 0);
    TestEqual(TEXT("Retry restores progress entrance"), F.Objective->GetRescueProgress(), 0.0f);
    TestEqual(TEXT("Retry restores independent integrity"), F.Objective->GetIntegrity(), 100.0f);
    F.Defeat(F.EnemyOne);
    F.Tick(24.0f);
    TestTrue(TEXT("Old caster callback cannot leave a new retry interfered"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualSnapshotTest,
    "Nilin.Objective.Ritual.SnapshotRebindValidationAndNoReplay", NLRitualTests::Flags)
bool FNLRitualSnapshotTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Snapshot fixture begins play"), F.IsReady())) return false;
    F.Tick(24.0f);
    F.Objective->RegisterInterferenceSource(TEXT("Caster.One"), F.EnemyOne.Actor);
    F.Objective->RegisterInterferenceSource(TEXT("Caster.Two"), F.EnemyTwo.Actor);
    const FNLObjectiveSnapshot Entrance = F.Objective->CaptureObjectiveSnapshot();
    FNLCheckpointSnapshot Checkpoint;
    Checkpoint.ContentRevision = TEXT("Ritual.Test.1");
    Checkpoint.RunId = FGuid::NewGuid();
    Checkpoint.LevelId = TEXT("Level.Ritual.Test");
    Checkpoint.NodeId = TEXT("Node.Ritual.Test");
    Checkpoint.EncounterId = TEXT("Encounter.Ritual.Test");
    Checkpoint.CheckpointId = TEXT("Checkpoint.Ritual.Test");
    Checkpoint.OrderedWaveIds.Add(TEXT("Wave.Ritual.Test"));
    Checkpoint.ObjectiveState = Entrance;
    FName Failure;
    TestTrue(TEXT("Objective snapshot is accepted by real SAVE-01 validation"), UNLCheckpointService::ValidateSnapshot(Checkpoint, Failure));
    TestTrue(TEXT("Objective restores scalar entrance"), F.Objective->RestoreObjectiveSnapshot(Entrance));
    TestTrue(TEXT("Restore waits for live source reconstruction"), F.Objective->IsAwaitingSourceRebuild());
    TestEqual(TEXT("Runtime actor references were not serialized"), F.Objective->GetInterferenceSourceCount(), 0);
    F.Tick(24.0f);
    TestTrue(TEXT("Restore cannot advance before source rebuilding completes"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 10.0f, .001f));
    TestTrue(TEXT("A known saved ID rebinds to a live reconstructed caster"), F.Objective->RegisterInterferenceSource(TEXT("Caster.One"), F.EnemyOne.Actor));
    TestEqual(TEXT("Unbound absent caster is explicitly discarded, never a ghost blocker"), F.Objective->FinishSourceRebuild(), 1);
    TestEqual(TEXT("Only the rebound living caster still interferes"), F.Objective->GetInterferenceSourceCount(), 1);
    F.Defeat(F.EnemyOne);
    F.Tick(24.0f);
    TestTrue(TEXT("Rebound source death resumes saved progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 20.0f, .001f));
    FNLObjectiveSnapshot Invalid = F.Objective->CaptureObjectiveSnapshot();
    Invalid.StableId = TEXT("Wrong.Objective");
    TestFalse(TEXT("Wrong objective ID rejects atomically"), F.Objective->RestoreObjectiveSnapshot(Invalid));
    Invalid.StableId = TEXT("Objective.Test.Ritual");
    Invalid.Integrity = std::numeric_limits<float>::quiet_NaN();
    TestFalse(TEXT("NaN integrity rejects atomically"), F.Objective->RestoreObjectiveSnapshot(Invalid));
    TestTrue(TEXT("Invalid loads leave current progress untouched"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), 20.0f, .001f));
    FNLObjectiveSnapshot Complete = F.Objective->CaptureObjectiveSnapshot();
    Complete.RescueProgress = 100.0f;
    Complete.bCompleted = true;
    Complete.InterferenceSourceIds.Reset();
    TestTrue(TEXT("Completed snapshot can restore completed state"), F.Objective->RestoreObjectiveSnapshot(Complete));
    F.Tick(1.0f);
    TestTrue(TEXT("Completed state is visible after loading"), F.Objective->IsRescueCompleted());
    TestEqual(TEXT("Loading terminal state never replays rescue rewards/events"), F.Objective->GetCompletionEventCount(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLRitualSourceValidationTest,
    "Nilin.Objective.Ritual.SourceLifetimeAndAtomicConfiguration", NLRitualTests::Flags)
bool FNLRitualSourceValidationTest::RunTest(const FString& Parameters)
{
    FWorld F;
    if (!TestTrue(TEXT("Validation fixture begins play"), F.IsReady())) return false;
    TestFalse(TEXT("None source ID is rejected"), F.Objective->RegisterInterferenceSource(NAME_None, F.EnemyOne.Actor));
    TestFalse(TEXT("Player cannot register as a hostile caster"), F.Objective->RegisterInterferenceSource(TEXT("Caster.Player"), F.Player.Actor));
    TestFalse(TEXT("Null source is rejected"), F.Objective->RegisterInterferenceSource(TEXT("Caster.Null"), nullptr));
    TestFalse(TEXT("Zero effective duration is rejected"), F.Objective->InitializeObjective(TEXT("Objective.Test.Ritual"), 100.0f, 0.0f));
    TestEqual(TEXT("Invalid configuration leaves GDD duration unchanged"), F.Objective->EffectiveRescueSeconds, 240.0f);
    F.Objective->RegisterInterferenceSource(TEXT("Caster.One"), F.EnemyOne.Actor);
    F.EnemyOne.Identity->Faction = ENLCombatFaction::Player;
    F.Tick(.1f);
    TestEqual(TEXT("A source that ceases to be a valid enemy is pruned"), F.Objective->GetInterferenceSourceCount(), 0);
    F.Objective->SetObjectiveActive(false);
    const float Progress = F.Objective->GetRescueProgress();
    F.Tick(10.0f);
    TestEqual(TEXT("Inactive ritual does not advance"), F.Objective->GetRescueProgress(), Progress);
    TestFalse(TEXT("Inactive ritual cannot acquire a caster"), F.Objective->RegisterInterferenceSource(TEXT("Caster.Two"), F.EnemyTwo.Actor));
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
