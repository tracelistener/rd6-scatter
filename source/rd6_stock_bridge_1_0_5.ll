; RD-6 1.0.5 stock-routine bindings. Research only: this code would write
; device GPIO and call stock MIDI/delay routines if executed on the RD-6.
; It is compiled and inspected offline, never run or installed.

; Only the three output-register addresses used by the tested frame emitter
; are accepted. The caller supplies stock GPIOB PB2 input state separately.
define void @rd6_stock_write_cb(ptr %ctx, i32 %address,
                                i32 %value) nounwind {
entry:
  switch i32 %address, label %ignore [
    i32 1207961624, label %write
    i32 1207961640, label %write
    i32 1207960600, label %write
    i32 1207960616, label %write
  ]

write:
  %register = inttoptr i32 %address to ptr
  store volatile i32 %value, ptr %register, align 4
  ret void

ignore:
  ret void
}

; Reserve eight slots for the next ordinary stock step, which can enqueue
; all eight voice bytes without checking capacity. Both the note-on and
; delayed note-off cursors share this 100-byte ring. If either cursor would
; be within eight slots after our write, omit this extra-hit MIDI byte while
; leaving the analog trigger path in rd6_apply_frame intact.
define void @rd6_stock_queue_cb(ptr %ctx, i32 %byte) nounwind {
entry:
  %base = inttoptr i32 536871688 to ptr ; 0x20000308
  %write_ptr = getelementptr i32, ptr %base, i32 6
  %on_ptr = getelementptr i32, ptr %base, i32 7
  %off_ptr = getelementptr i32, ptr %base, i32 8
  %write = load volatile i32, ptr %write_ptr, align 4
  %on = load volatile i32, ptr %on_ptr, align 4
  %off = load volatile i32, ptr %off_ptr, align 4
  %increment = add i32 %write, 1
  %next = urem i32 %increment, 100
  %on_distance_numerator = add i32 %on, 100
  %on_distance_offset = sub i32 %on_distance_numerator, %next
  %on_distance = urem i32 %on_distance_offset, 100
  %off_distance_numerator = add i32 %off, 100
  %off_distance_offset = sub i32 %off_distance_numerator, %next
  %off_distance = urem i32 %off_distance_offset, 100
  %on_room = icmp ugt i32 %on_distance, 8
  %off_room = icmp ugt i32 %off_distance, 8
  %room = and i1 %on_room, %off_room
  br i1 %room, label %enqueue, label %skip

enqueue:
  %fn = inttoptr i32 134229461 to ptr
  %result = call i32 %fn(i32 %byte)
  ret void

skip:
  ret void
}

; TIMER14 can preempt the stock TIMER13 producer while its cursor update is
; incomplete. Extra-hit MIDI therefore stays disabled in the timer path.
; The MIDI-capable callback above remains research-only until a serialized
; producer design is verified. Regular stock steps still queue normally.
define void @rd6_stock_queue_analog_only_cb(ptr %ctx, i32 %byte) nounwind {
entry:
  ret void
}

; Stock calibrated-loop delay at 0x08003196, Thumb state bit set. Only the
; MIDI-capable research bridge below binds it; it is never reachable from the
; TIMER14 body (see rd6_timer_callgraph_audit.py).
define void @rd6_stock_delay_cb(ptr %ctx, i32 %iterations) nounwind {
entry:
  %fn = inttoptr i32 134230423 to ptr
  call void %fn(i32 %iterations)
  ret void
}

; TIMER14 binding of the delay callback. The TIMER14 body passes its hits
; through rd6_analog_only_hits first, which drops any clap that would need
; the PB2 pre-pulse, so the frame applier never reaches its delay call on
; this path; this no-op keeps the stock busy loop out of the TIMER14 call
; graph even so. It performs no PB2 pre-action and no wait.
define void @rd6_stock_delay_analog_only_cb(ptr %ctx, i32 %iterations) nounwind {
entry:
  ret void
}

define void @rd6_stock_apply_frame(ptr readonly %frame) nounwind {
entry:
  %short = inttoptr i32 536875416 to ptr   ; 0x20001198
  %clap = inttoptr i32 536875420 to ptr    ; 0x2000119C
  %flag = inttoptr i32 536871772 to ptr    ; 0x2000035C
  call void @rd6_apply_frame(ptr %frame, ptr null,
                             ptr @rd6_stock_write_cb,
                             ptr @rd6_stock_queue_cb,
                             ptr @rd6_stock_delay_cb,
                             ptr %short, ptr %clap, ptr %flag)
  ret void
}

; Analog-only applier for TIMER14: no MIDI byte and no stock delay binding.
define void @rd6_stock_apply_frame_analog_only(ptr readonly %frame) nounwind {
entry:
  %short = inttoptr i32 536875416 to ptr   ; 0x20001198
  %clap = inttoptr i32 536875420 to ptr    ; 0x2000119C
  %flag = inttoptr i32 536871772 to ptr    ; 0x2000035C
  call void @rd6_apply_frame(ptr %frame, ptr null,
                             ptr @rd6_stock_write_cb,
                             ptr @rd6_stock_queue_analog_only_cb,
                             ptr @rd6_stock_delay_analog_only_cb,
                             ptr %short, ptr %clap, ptr %flag)
  ret void
}

; Timer-side extra-hit emitter. It uses 40 bytes of aligned stack storage.
; Never invoke for a regular step: the stock dispatcher already fires those.
define i32 @rd6_stock_fire_hits(i32 %hits, i32 %pb2_high) nounwind {
entry:
  %frame = alloca [40 x i8], align 4
  %frame_ptr = getelementptr [40 x i8], ptr %frame, i32 0, i32 0
  %count = call i32 @rd6_output_frame(i32 %hits, i32 %pb2_high,
                                      ptr %frame_ptr)
  call void @rd6_stock_apply_frame(ptr %frame_ptr)
  ret i32 %count
}

; The TIMER14 body passes only rd6_analog_only_hits output here, so the frame
; never carries a PB2 pre-action or a delay request on this path.
define i32 @rd6_stock_fire_hits_analog_only(i32 %hits, i32 %pb2_high) nounwind {
entry:
  %frame = alloca [40 x i8], align 4
  %frame_ptr = getelementptr [40 x i8], ptr %frame, i32 0, i32 0
  %count = call i32 @rd6_output_frame(i32 %hits, i32 %pb2_high,
                                      ptr %frame_ptr)
  call void @rd6_stock_apply_frame_analog_only(ptr %frame_ptr)
  ret i32 %count
}
