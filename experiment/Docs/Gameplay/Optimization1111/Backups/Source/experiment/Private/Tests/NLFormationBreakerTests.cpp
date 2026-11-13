#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLTalismanAttackComponent.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Objective/NLRitualObjective.h"

/** Only navigation is bypassed in this fixture. Slot requests, timeline, attack delegates,
 *  interference registration and swept projectile damage all execute production code. */
struct FNLFormationBreakerTestAccess
{
    static AActor* Target(UNLEnemyBrainComponent* Brain) { return Brain->TargetActor.Get(); }
    static FGuid Reservation(UNLEnemyBrainComponent* Brain) { return Brain->ReservationId; }
    static void AtCastingPosition(UNLEnemyBrainComponent* Brain)
    {
        Brain->SetState(ENLEnemyState::WaitForSlot);
        Brain->RetryElapsed = .4f;
    }
    static void Step(UNLEnemyBrainComponent* Brain, float Delta)
    {
        Brain->StateElapsed += Delta;
        Brain->RetryElapsed += Delta;
        if (Brain->State == ENLEnemyState::WaitForSlot) Brain->UpdateWaitForSlot(Delta);
        else if (Brain->State == ENLEnemyState::Telegraph || Brain->State == ENLEnemyState::Attack
            || Brain->State == ENLEnemyState::Recover) Brain->UpdateAttackTimeline();
    }
};

namespace NLFormationTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FWorld
    {
        UWorld* World = nullptr;
        ANLRitualObjective* Objective = nullptr;
        ANLEnemyCharacter* Enemy = nullptr;
        UNLEnemyBrainComponent* Brain = nullptr;
        UNLAttackDefinition* Attack = nullptr;
        UNLAttackDirectorSubsystem* Director = nullptr;
        uint64 SavedFrameCounter = GFrameCounter;

        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinFormation_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(World->WorldType).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Objective = World->SpawnActor<ANLRitualObjective>();
            if (!Objective) return;
            Objective->InitializeObjective(TEXT("Objective.Test.Formation"));
            Objective->AllowedAttackDefinitionIds.Add(TEXT("Attack.Test.Formation"));
            Attack = NewObject<UNLAttackDefinition>(World);
            Attack->StableId = TEXT("Attack.Test.Formation");
            Attack->Damage = 8;
            Director = World->GetSubsystem<UNLAttackDirectorSubsystem>();
            const FTransform Spawn(FRotator::ZeroRotator, FVector(-700, 0, 88));
            Enemy = World->SpawnActorDeferred<ANLEnemyCharacter>(ANLEnemyCharacter::StaticClass(), Spawn,
                nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Enemy) return;
            Brain = Enemy->GetEnemyBrain();
            Brain->Role = ENLEnemyRole::FormationBreaker;
            Brain->FormationObjectiveId = Objective->ObjectiveStableId;
            Brain->AttackRange = 1000;
            Brain->MinimumRangedDistance = 200;
            Brain->PreferredRangedDistance = 650;
            Brain->TelegraphSeconds = 1.8f;
            Brain->AttackSeconds = 1.7f;
            Brain->RecoverSeconds = 1.2f;
            Brain->ProjectileSpeed = 1000;
            Brain->RangedAttackDefinition = Attack;
            Enemy->EnemyAttackDefinition = Attack;
            Enemy->Vitals->MaxHealth = 45;
            Enemy->FinishSpawning(Spawn);
            Enemy->GetCharacterMovement()->DisableMovement();
            Enemy->SetCombatEnabled(true);
            Brain->SetComponentTickEnabled(false); // Navigation is verified separately in the actual map.
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
        bool Ready() const { return World && Objective && Enemy && Brain && Attack && Director; }
        void Step(float Seconds, bool bDriveTimeline = true)
        {
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(Seconds / .05f));
            for (int32 I=0; I<Steps; ++I)
            {
                const float Delta = FMath::Max(0.0f, FMath::Min(.05f, Seconds-I*.05f));
                if (bDriveTimeline) FNLFormationBreakerTestAccess::Step(Brain, Delta);
                World->Tick(LEVELTICK_All, Delta);
                ++GFrameCounter;
            }
        }
        bool StartCast()
        {
            FNLFormationBreakerTestAccess::AtCastingPosition(Brain);
            Step(.05f);
            return Brain->GetState() == ENLEnemyState::Telegraph;
        }
        bool Channel()
        {
            if (!StartCast()) return false;
            Step(1.85f);
            return Enemy->TalismanAttack->IsInterfering();
        }
        int32 ProjectileCount() const
        {
            int32 Count=0;
            for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
                if (!It->IsActorBeingDestroyed()) ++Count;
            return Count;
        }
        FNLCombatResult PlayerHit(float Damage)
        {
            AActor* Player = World->SpawnActor<AActor>();
            UNLCombatIdentityComponent* Id = NewObject<UNLCombatIdentityComponent>(Player);
            Id->Faction = ENLCombatFaction::Player;
            Player->AddInstanceComponent(Id); Id->RegisterComponent();
            UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Player);
            Player->AddInstanceComponent(Vitals); Vitals->RegisterComponent(); Vitals->ResetVitals();
            UNLAttackDefinition* Hit = NewObject<UNLAttackDefinition>(World);
            Hit->StableId = TEXT("Attack.Test.FormationInterrupt"); Hit->Damage = Damage;
            FNLCombatContact Contact;
            Contact.AttackInstanceId = FGuid::NewGuid();
            Contact.SourceRuntimeId = Id->EnsureRuntimeId();
            Contact.TargetRuntimeId = Enemy->CombatIdentity->EnsureRuntimeId();
            Contact.ProjectileGeneration = INDEX_NONE;
            Contact.ContactTimeSeconds = World->GetTimeSeconds();
            Contact.AttackDefinitionId = Hit->StableId;
            return World->GetSubsystem<UNLCombatResolverSubsystem>()->ResolveContact(Player, Enemy, Contact, Hit);
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFormationWarningAndChannelTest,
    "Nilin.Enemy.FormationBreaker.WarningChannelProjectileAndBoundedRelease", NLFormationTests::Flags)
bool FNLFormationWarningAndChannelTest::RunTest(const FString& Parameters)
{
    NLFormationTests::FWorld F;
    if (!TestTrue(TEXT("Real formation fixture"), F.Ready())) return false;
    TestTrue(TEXT("Objective is the exclusive target"), FNLFormationBreakerTestAccess::Target(F.Brain) == F.Objective);
    if (!TestTrue(TEXT("Acquires a real attack reservation"), F.StartCast())) return false;
    TestEqual(TEXT("One high-threat reservation"), F.Director->GetReservationCount(), 1);
    FNLAttackSlotRequest GrantedRequest;
    double ExpiresAt = 0.0;
    const FGuid ReservationId = FNLFormationBreakerTestAccess::Reservation(F.Brain);
    const bool bHasRequest = F.Director->GetReservationRequest(ReservationId, GrantedRequest, ExpiresAt);
    TestTrue(TEXT("Live granted reservation targets objective with the exact attacker and high-threat slot"),
        bHasRequest && GrantedRequest.Target == F.Objective && GrantedRequest.Attacker == F.Enemy
        && GrantedRequest.TargetRuntimeId == F.Objective->CombatIdentity->GetRuntimeId()
        && GrantedRequest.EnemyRuntimeId == F.Enemy->CombatIdentity->GetRuntimeId()
        && GrantedRequest.Slot == ENLAttackSlot::HighThreat);
    const auto Diagnostics = F.Director->GetRecentDiagnostics();
    // Diagnostic history deliberately drops strong Actor references; its stable identity
    // and the actual live reservation must agree, rather than comparing a cleared pointer.
    TestTrue(TEXT("Granted diagnostic preserves objective identity and high-threat slot"),
        Diagnostics.ContainsByPredicate([&F, ReservationId](const FNLAttackDirectorDiagnostic& D)
        {
            return D.bGranted && D.ReservationId == ReservationId
                && D.Request.TargetRuntimeId == F.Objective->CombatIdentity->GetRuntimeId()
                && D.Request.EnemyRuntimeId == F.Enemy->CombatIdentity->GetRuntimeId()
                && D.Request.Slot == ENLAttackSlot::HighThreat;
        }));
    F.Step(1.4f);
    TestEqual(TEXT("No interference before full warning"), F.Objective->GetInterferenceSourceCount(), 0);
    TestEqual(TEXT("No projectile before full warning"), F.ProjectileCount(), 0);
    F.Step(.45f);
    TestTrue(TEXT("Reserved native attack opens interference"), F.Enemy->TalismanAttack->IsInterfering());
    TestEqual(TEXT("One stable source per caster"), F.Objective->GetInterferenceSourceCount(), 1);
    const float Progress = F.Objective->GetRescueProgress();
    F.Step(.8f);
    TestTrue(TEXT("Interference stops rescue progress"), FMath::IsNearlyEqual(F.Objective->GetRescueProgress(), Progress, .001f));
    TestEqual(TEXT("Real swept projectile damages objective through resolver"), F.Objective->GetIntegrity(), 92.0f);
    F.Step(1.0f);
    TestEqual(TEXT("Finite channel releases source automatically"), F.Objective->GetInterferenceSourceCount(), 0);
    TestFalse(TEXT("Component no longer channels"), F.Enemy->TalismanAttack->IsInterfering());
    F.Step(1.3f);
    TestEqual(TEXT("Recovery releases high-threat reservation"), F.Director->GetReservationCount(), 0);
    TestTrue(TEXT("Progress resumes after channel"), F.Objective->GetRescueProgress() > Progress);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFormationInterruptAndLifecycleTest,
    "Nilin.Enemy.FormationBreaker.InterruptPauseDeathAndResetClearSources", NLFormationTests::Flags)
bool FNLFormationInterruptAndLifecycleTest::RunTest(const FString& Parameters)
{
    for (int32 Mode=0; Mode<5; ++Mode)
    {
        NLFormationTests::FWorld F;
        if (!TestTrue(TEXT("Lifecycle fixture"), F.Ready() && F.Channel())) return false;
        if (Mode == 0) F.PlayerHit(1.0f);
        else if (Mode == 1) F.Enemy->SetLabPaused(true);
        else if (Mode == 2) F.PlayerHit(100.0f);
        else if (Mode == 3) F.Enemy->ResetForEncounter();
        else F.Enemy->Destroy();
        TestEqual(TEXT("Lifecycle event clears objective interference immediately"), F.Objective->GetInterferenceSourceCount(), 0);
        TestEqual(TEXT("Lifecycle event frees attack reservation"), F.Director->GetReservationCount(), 0);
        if (Mode == 0) TestEqual(TEXT("Actual damaging contact staggers channel"), F.Brain->GetState(), ENLEnemyState::Staggered);
        if (Mode == 1)
        {
            F.Enemy->SetLabPaused(false);
            TestTrue(TEXT("Pause resume must request a fresh warning"), F.StartCast());
            F.Step(1.0f);
            TestEqual(TEXT("Resume cannot instantly restore channel"), F.Objective->GetInterferenceSourceCount(), 0);
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLFormationTargetGateTest,
    "Nilin.Enemy.FormationBreaker.TargetIdentityAndInactiveGate", NLFormationTests::Flags)
bool FNLFormationTargetGateTest::RunTest(const FString& Parameters)
{
    {
        NLFormationTests::FWorld Phase;
        if (!TestTrue(TEXT("Live channel before phase restore"), Phase.Ready() && Phase.Channel())) return false;
        const int32 ShotsBefore = Phase.ProjectileCount();
        FNLObjectiveSnapshot Snapshot;
        Snapshot.StableId = Phase.Objective->ObjectiveStableId;
        Snapshot.Integrity = Phase.Objective->GetIntegrity();
        Snapshot.RescueProgress = 25.0f;
        TestTrue(TEXT("Real phase restore creates a completion candidate"),
            Phase.Objective->RestoreObjectivePhaseSnapshot(Snapshot, 25.0f) && Phase.Objective->IsCompletionPending());
        TestEqual(TEXT("Phase candidate clears existing channel immediately"), Phase.Objective->GetInterferenceSourceCount(), 0);
        TestFalse(TEXT("Caster releases its local objective binding"), Phase.Enemy->TalismanAttack->IsInterfering());
        TestEqual(TEXT("Phase candidate cancels high-threat reservation"), Phase.Director->GetReservationCount(), 0);
        TestEqual(TEXT("Restoration does not fire another projectile"), Phase.ProjectileCount(), ShotsBefore);
        Phase.Objective->SetObjectiveActive(false);
        Phase.Brain->ResetBrain();
        TestNull(TEXT("Phase preparation cannot reacquire ritual target"), FNLFormationBreakerTestAccess::Target(Phase.Brain));
    }
    NLFormationTests::FWorld F;
    if (!TestTrue(TEXT("Target fixture"), F.Ready() && F.Channel())) return false;
    F.Objective->SetCombatPaused(true);
    TestEqual(TEXT("Objective pause immediately removes registered interference"), F.Objective->GetInterferenceSourceCount(), 0);
    TestEqual(TEXT("Objective pause cancels reservation"), F.Director->GetReservationCount(), 0);
    F.Objective->SetCombatPaused(false);
    F.Brain->FormationObjectiveId = TEXT("Missing.Objective");
    F.Brain->ResetBrain();
    TestNull(TEXT("Missing authored objective cannot fall back to a player"), FNLFormationBreakerTestAccess::Target(F.Brain));
    F.Brain->FormationObjectiveId = F.Objective->ObjectiveStableId;
    ANLRitualObjective* Duplicate = F.World->SpawnActor<ANLRitualObjective>();
    Duplicate->InitializeObjective(F.Objective->ObjectiveStableId);
    F.Brain->ResetBrain();
    TestNull(TEXT("Duplicate authored objective is not selected arbitrarily"), FNLFormationBreakerTestAccess::Target(F.Brain));
    Duplicate->Destroy();
    F.Objective->SetObjectiveActive(false);
    F.Brain->ResetBrain();
    TestNull(TEXT("Inactive authored objective remains unavailable"), FNLFormationBreakerTestAccess::Target(F.Brain));
    TestEqual(TEXT("Unavailable objective leaves no slot"), F.Director->GetReservationCount(), 0);
    return true;
}

#endif
