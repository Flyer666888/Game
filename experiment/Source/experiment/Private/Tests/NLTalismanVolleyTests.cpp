#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLTalismanAttackComponent.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Materials/Material.h"
#include "Misc/AutomationTest.h"

/** Bypass navigation only; warning, reservation, volley and collision stay native. */
struct FNLTalismanVolleyTestAccess
{
    static void AtPosition(UNLEnemyBrainComponent* Brain, AActor* Target)
    {
        Brain->TargetActor = Target;
        Brain->StartBrain();
        Brain->SetState(ENLEnemyState::WaitForSlot);
        Brain->RetryElapsed = 1.0f;
    }
    static float WarningSeconds(const UNLEnemyBrainComponent* Brain) { return Brain->GetTelegraphDuration(); }
    static void SeedVolley(UNLTalismanAttackComponent* Attack, int32 Seed) { Attack->VolleyRandom.Initialize(Seed); }
    static void Step(UNLEnemyBrainComponent* Brain, float Delta)
    {
        Brain->StateElapsed += Delta;
        Brain->RetryElapsed += Delta;
        if (Brain->GetState() == ENLEnemyState::WaitForSlot) Brain->UpdateWaitForSlot(Delta);
        else if (Brain->GetState() == ENLEnemyState::Telegraph || Brain->GetState() == ENLEnemyState::Attack
            || Brain->GetState() == ENLEnemyState::Recover) Brain->UpdateAttackTimeline();
    }
};

namespace NLTalismanVolleyTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FWorld
    {
        UWorld* World = nullptr;
        ANLEnemyCharacter* Enemy = nullptr;
        UNLEnemyBrainComponent* Brain = nullptr;
        AActor* Target = nullptr;
        UNLCombatVitalsComponent* Vitals = nullptr;
        uint64 SavedFrame = GFrameCounter;
        FWorld(bool bGolden = false)
        {
            if (!GEngine) return;
            const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
                .CreatePhysicsScene(true).ShouldSimulatePhysics(false).EnableTraceCollision(true)
                .CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false,
                FName(*FString::Printf(TEXT("NilinVolley_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
                nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            World->GetWorldSettings()->NotifyBeginPlay();
            Target = World->SpawnActor<AActor>();
            USphereComponent* Body = NewObject<USphereComponent>(Target);
            Body->InitSphereRadius(40);
            Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Body->SetCollisionObjectType(ECC_Pawn);
            Body->SetCollisionResponseToAllChannels(ECR_Ignore);
            Body->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
            Body->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
            Target->SetRootComponent(Body); Target->AddInstanceComponent(Body); Body->RegisterComponent();
            Target->SetActorLocation(FVector(700, 0, 100));
            UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Target);
            Identity->Faction = ENLCombatFaction::Player;
            Target->AddInstanceComponent(Identity); Identity->RegisterComponent(); Identity->EnsureRuntimeId();
            Vitals = NewObject<UNLCombatVitalsComponent>(Target);
            Vitals->DamageProtectionSeconds = 0;
            Target->AddInstanceComponent(Vitals); Vitals->RegisterComponent(); Vitals->ResetVitals();
            const FTransform Spawn(FRotator::ZeroRotator, FVector(0, 0, 88));
            Enemy = World->SpawnActorDeferred<ANLEnemyCharacter>(ANLEnemyCharacter::StaticClass(), Spawn,
                nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            if (!Enemy) return;
            Brain = Enemy->GetEnemyBrain();
            Brain->Role = ENLEnemyRole::TalismanCaster;
            Brain->AttackRange = 1600;
            Brain->MinimumRangedDistance = 150;
            Brain->TargetAimOffset = FVector::ZeroVector;
            Brain->TelegraphSeconds = 1.0f;
            Brain->AttackSeconds = .4f;
            Brain->RecoverSeconds = 1.1f;
            Brain->ProjectileSpeed = 1200;
            UNLAttackDefinition* Attack = NewObject<UNLAttackDefinition>(World);
            Attack->StableId = TEXT("Attack.Test.TalismanVolley");
            Attack->Damage = 8;
            Attack->bCanBeBlocked = false;
            Attack->bCanBeParried = false;
            Brain->RangedAttackDefinition = Attack;
            Enemy->EnemyAttackDefinition = Attack;
            Enemy->TalismanAttack->MuzzleSocketName = NAME_None;
            Enemy->TalismanAttack->FallbackMuzzleOffset = FVector(0, 0, 12);
            Enemy->TalismanAttack->ProjectileMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
            if (bGolden)
            {
                Enemy->TalismanAttack->bFloatBeforeHand = true;
                Enemy->TalismanAttack->TalismanMesh = LoadObject<UStaticMesh>(nullptr,
                    TEXT("/Game/ReversedScale/Weapons/TalismanJade1104/SM_Nilin_JadeTalisman.SM_Nilin_JadeTalisman"));
                Enemy->TalismanAttack->ProjectileMaterial = LoadObject<UMaterialInterface>(nullptr,
                    TEXT("/Game/ReversedScale/Weapons/TalismanJade1104/M_TalismanGoldenOrb.M_TalismanGoldenOrb"));
            }
            Enemy->FinishSpawning(Spawn);
            Enemy->GetCharacterMovement()->DisableMovement();
            Enemy->SetCombatEnabled(true);
            Enemy->SetActorTickEnabled(false);
            Brain->SetComponentTickEnabled(false);
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            GFrameCounter = SavedFrame;
        }
        bool Ready() const { return World && Enemy && Brain && Target && Vitals; }
        void Step(float Seconds, bool bTimeline = true)
        {
            const int32 Count = FMath::Max(1, FMath::CeilToInt(Seconds / .01f));
            for (int32 I = 0; I < Count; ++I)
            {
                const float Delta = FMath::Min(.01f, FMath::Max(0.0f, Seconds - I * .01f));
                if (bTimeline) FNLTalismanVolleyTestAccess::Step(Brain, Delta);
                World->Tick(LEVELTICK_All, Delta);
                ++GFrameCounter;
            }
        }
        bool StartCast()
        {
            FNLTalismanVolleyTestAccess::AtPosition(Brain, Target);
            Step(.01f);
            return Brain->GetState() == ENLEnemyState::Telegraph;
        }
        TArray<ANLCombatProjectile*> Projectiles() const
        {
            TArray<ANLCombatProjectile*> Result;
            for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
                if (!It->IsActorBeingDestroyed()) Result.Add(*It);
            return Result;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLTalismanVolleyCountTest,
    "Nilin.Enemy.Talisman.Volley.RandomBoundedFanAndSharedDamage", NLTalismanVolleyTests::Flags)
bool FNLTalismanVolleyCountTest::RunTest(const FString& Parameters)
{
    for (int32 Mode = 0; Mode < 5; ++Mode)
    {
        NLTalismanVolleyTests::FWorld F;
        if (!TestTrue(TEXT("Native caster fixture"), F.Ready())) return false;
        if (Mode < 3)
            F.Enemy->TalismanAttack->MinimumVolleyProjectiles = F.Enemy->TalismanAttack->MaximumVolleyProjectiles = Mode + 2;
        if (Mode == 4) F.Enemy->TalismanAttack->VolleyHalfSpreadDegrees = 0; // Exact overlap tests damage de-duplication.
        if (!TestTrue(TEXT("Real director reservation opens warning"), F.StartCast())) return false;
        const float Warning = FNLTalismanVolleyTestAccess::WarningSeconds(F.Brain);
        F.Step(Warning - .05f);
        TestEqual(TEXT("A volley never fires before its warning completes"), F.Projectiles().Num(), 0);
        F.Step(.07f);
        const auto Shots = F.Projectiles();
        TestTrue(TEXT("Each cast emits between two and four projectiles"), Shots.Num() >= 2 && Shots.Num() <= 4);
        if (Mode < 3) TestEqual(TEXT("Configured count endpoints execute actual volleys"), Shots.Num(), Mode + 2);
        const FGuid AttackId = F.Brain->GetAttackInstanceId();
        bool bCenterShot = false;
        for (ANLCombatProjectile* Shot : Shots)
        {
            TestEqual(TEXT("All balls retain their single director attack identity"), Shot->GetAttackInstanceId(), AttackId);
            TestTrue(TEXT("Fan spread stays inside the configured cone"),
                FVector::DotProduct(Shot->GetActorForwardVector(), FVector::ForwardVector) >= FMath::Cos(FMath::DegreesToRadians(12.1f)));
            bCenterShot |= Shot->GetActorForwardVector().Equals(FVector::ForwardVector, .001);
        }
        TestTrue(TEXT("A center shot still threatens a stationary target"), bCenterShot);
        F.Brain->OnAttackWindowStarted.Broadcast(F.Enemy, F.Target);
        TestEqual(TEXT("Repeated window notifications cannot duplicate a volley"), F.Projectiles().Num(), Shots.Num());
        if (Mode == 4)
        {
            F.Step(.7f, false);
            TestEqual(TEXT("Overlapping balls from one warning cannot multiply health damage"), F.Vitals->GetHealth(), 92.0f);
        }
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLTalismanVolleyPauseTest,
    "Nilin.Enemy.Talisman.Volley.PauseCancelsWithoutDelayedShots", NLTalismanVolleyTests::Flags)
bool FNLTalismanVolleyPauseTest::RunTest(const FString& Parameters)
{
    NLTalismanVolleyTests::FWorld F;
    if (!TestTrue(TEXT("Caster begins a warning"), F.Ready() && F.StartCast())) return false;
    F.Step(.2f);
    F.Enemy->SetLabPaused(true);
    F.Step(2.0f, false);
    F.Brain->OnAttackWindowStarted.Broadcast(F.Enemy, F.Target);
    TestEqual(TEXT("Pause invalidates the entire pending volley"), F.Projectiles().Num(), 0);
    TestEqual(TEXT("No cancelled projectile can damage the player"), F.Vitals->GetHealth(), 100.0f);
    F.Enemy->SetLabPaused(false);
    if (!TestTrue(TEXT("Resume requests a fresh warning"), F.StartCast())) return false;
    F.Step(FNLTalismanVolleyTestAccess::WarningSeconds(F.Brain) - .05f);
    TestEqual(TEXT("Resume never skips the new warning"), F.Projectiles().Num(), 0);
    F.Step(.07f);
    TestTrue(TEXT("One new legal volley fires after the full warning"), F.Projectiles().Num() >= 2);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLTalismanSeededGoldenVolleyTest,
    "Nilin.Enemy.Talisman.Volley.RandomTwoThreeFourGoldenMaterialAndSpeed", NLTalismanVolleyTests::Flags)
bool FNLTalismanSeededGoldenVolleyTest::RunTest(const FString& Parameters)
{
    NLTalismanVolleyTests::FWorld F(true);
    if (!TestTrue(TEXT("Authored golden caster fixture"), F.Ready())) return false;
    UNLTalismanAttackComponent* Attack = F.Enemy->TalismanAttack;
    if (!TestTrue(TEXT("The accepted jade prop and golden orb material remain available"),
        Attack->TalismanMesh != nullptr && Attack->ProjectileMaterial != nullptr)) return false;
    FNLTalismanVolleyTestAccess::SeedVolley(Attack, 42);
    TSet<int32> ObservedCounts;
    for (int32 Cast = 0; Cast < 12; ++Cast)
    {
        ANLCombatProjectile::DestroyWorldProjectiles(F.World);
        F.Brain->ResetBrain();
        if (!TestTrue(TEXT("Each cast obtains a fresh real reservation and warning"), F.StartCast())) return false;
        F.Step(FNLTalismanVolleyTestAccess::WarningSeconds(F.Brain) + .02f);
        const auto Shots = F.Projectiles();
        ObservedCounts.Add(Shots.Num());
        TestTrue(TEXT("Random cast stays in the actual 2–4 ball budget"), Shots.Num() >= 2 && Shots.Num() <= 4);
        TArray<FVector> Positions;
        for (ANLCombatProjectile* Shot : Shots)
        {
            Positions.Add(Shot->GetActorLocation());
            TestTrue(TEXT("Each emitted ball retains the authored golden material"),
                Shot->Visual->GetMaterial(0) == Attack->ProjectileMaterial);
        }
        F.Step(.05f, false);
        for (int32 Index = 0; Index < Shots.Num(); ++Index)
            TestTrue(TEXT("Every ball moves at the configured caster projectile speed"),
                FMath::IsNearlyEqual(FVector::Distance(Shots[Index]->GetActorLocation(), Positions[Index]),
                    F.Brain->ProjectileSpeed * .05f, .1));
    }
    TestTrue(TEXT("The seeded real volley sequence produces two, three and four projectiles"),
        ObservedCounts.Num() == 3 && ObservedCounts.Contains(2) && ObservedCounts.Contains(3) && ObservedCounts.Contains(4));
    return !HasAnyErrors();
}

#endif
