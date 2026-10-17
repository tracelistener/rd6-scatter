; RD-6 1.0.5 TIMER14 hook body, offline research only.
; The site stub calls original pulse maintenance, saves its volatile register
; results, then supplies state/command pointers from unresolved literals.
; This body runs the scheduler and emits a nonzero extra hit only, after the
; analog-only filter has removed any clap that would need the stock PB2
; pre-pulse and its 200-iteration busy delay (never run inside TIMER14).
; The guard receives the stock transport structure 0x20000BB4 (+0 playing
; word, +8 step) and fires nothing while the playing word is 0.
define void @rd6_timer_after_maintenance(ptr %state, ptr %command) nounwind {
entry:
  %clap_ptr = inttoptr i32 536875420 to ptr ; 0x2000119C
  %clap = load volatile i32, ptr %clap_ptr, align 4
  %pattern = inttoptr i32 536873628 to ptr  ; 0x20000A9C
  %transport = inttoptr i32 536873908 to ptr ; 0x20000BB4: +0 playing, +8 step
  %hits = call i32 @rd6_guarded_timer_tick(ptr %state, ptr %command,
                                           ptr %pattern, i32 %clap,
                                           i32 18, ptr %transport)
  %active = icmp ne i32 %hits, 0
  br i1 %active, label %emit, label %done

emit:
  ; Stock 0x08002EE4 reads GPIOB ISTAT bit 2 for clap pre-pulse.
  %pb_istat = inttoptr i32 1207960592 to ptr ; 0x48000410
  %input = load volatile i32, ptr %pb_istat, align 4
  %pb2 = and i32 %input, 4
  %high = icmp ne i32 %pb2, 0
  %pb2_high = zext i1 %high to i32
  %analog = call i32 @rd6_analog_only_hits(i32 %hits, i32 %pb2_high)
  %has_analog = icmp ne i32 %analog, 0
  br i1 %has_analog, label %fire, label %done

fire:
  %notes = call i32 @rd6_stock_fire_hits_analog_only(i32 %analog, i32 %pb2_high)
  br label %done

done:
  ret void
}
