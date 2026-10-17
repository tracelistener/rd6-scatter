; Offline RD-6 1.0.5 Scatter core prototype.
; Pure functions: no peripheral writes, USB, MIDI, SysEx, or flash routines.
; Pattern pointer addresses the RD-6 structure at 0x20000A9C.
; Modes: 0=off, 1=stutter, 2=reverse, 3=shuffle, 4=ratchet.
target triple = "thumbv7em-none-eabi"

@rd6_note_bits = private constant [8 x i32] [i32 2, i32 4, i32 8,
  i32 16, i32 32, i32 128, i32 256, i32 64]
@rd6_note_numbers = private constant [8 x i8] [i8 36, i8 40, i8 45,
  i8 50, i8 51, i8 46, i8 42, i8 39]
@rd6_io_address = private constant [8 x i32] [
  i32 1207961624, i32 1207961624, i32 1207961624, i32 1207961624,
  i32 1207960600, i32 1207961624, i32 1207961624, i32 1207961624]
@rd6_io_value = private constant [8 x i32] [
  i32 8192, i32 16384, i32 32768, i32 1,
  i32 32768, i32 2, i32 4, i32 512]

define i32 @rd6_source_step(i32 %step,i32 %length,i32 %mode,i32 %depth) nounwind {
entry:
  %slice = icmp eq i32 %mode,1
  %lo = icmp uge i32 %length,2
  %hi = icmp ule i32 %length,16
  %lenok = and i1 %lo,%hi
  %stepok = icmp ult i32 %step,%length
  %dlo = icmp uge i32 %depth,1
  %dhi = icmp ule i32 %depth,4
  %dok = and i1 %dlo,%dhi
  %v0 = and i1 %lenok,%stepok
  %v1 = and i1 %slice,%dok
  %valid = and i1 %v0,%v1
  br i1 %valid,label %map,label %fallback
fallback:
  ret i32 %step
map:
  %upper = icmp uge i32 %step,8
  %index = and i32 %step,7
  %shift = shl i32 %index,2
  %table1 = select i1 %upper,i32 4275861076,i32 3130536464
  %table2 = select i1 %upper,i32 3707672728,i32 1417023504
  %table3 = select i1 %upper,i32 4023167880,i32 1732518656
  %table4 = select i1 %upper,i32 4277954372,i32 3096981504
  %d2 = icmp eq i32 %depth,2
  %d3 = icmp eq i32 %depth,3
  %d4 = icmp eq i32 %depth,4
  %t2 = select i1 %d2,i32 %table2,i32 %table1
  %t3 = select i1 %d3,i32 %table3,i32 %t2
  %table = select i1 %d4,i32 %table4,i32 %t3
  %raw = lshr i32 %table,%shift
  %nibble = and i32 %raw,15
  %source = urem i32 %nibble,%length
  ret i32 %source
}


; Hook-facing mask remap. Keep the exact stock mask for off/ratchet and for
; invalid transport or pattern parameters. Source-step modes affect only the
; voice tests after the stock pattern-edit path has finished.
define i32 @rd6_legacy_source_mask(i32 %step,i32 %length,i32 %mode,i32 %depth,i32 %stock_mask) nounwind {
entry:
  %source = call i32 @rd6_source_step(i32 %step,i32 %length,i32 %mode,i32 %depth)
  %slice = icmp eq i32 %mode,1
  %cut = icmp eq i32 %mode,2
  %dlo = icmp uge i32 %depth,1
  %dhi = icmp ule i32 %depth,4
  %valid = and i1 %dlo,%dhi
  %safe = and i32 %step,15
  %d2 = icmp eq i32 %depth,2
  %d3 = icmp eq i32 %depth,3
  %d4 = icmp eq i32 %depth,4
  %m2 = select i1 %d2,i32 23130,i32 30583
  %m3 = select i1 %d3,i32 3855,i32 %m2
  %m4 = select i1 %d4,i32 4681,i32 %m3
  %bit = lshr i32 %m4,%safe
  %on = and i32 %bit,1
  %quiet = icmp eq i32 %on,0
  %cutquiet = and i1 %cut,%quiet
  %mute = and i1 %valid,%cutquiet
  %slicev = and i1 %slice,%valid
  %mapped = shl i32 1,%source
  %base = select i1 %slicev,i32 %mapped,i32 %stock_mask
  %answer = select i1 %mute,i32 0,i32 %base
  ret i32 %answer
}

; Proposed live control: channel-filtered MIDI CC 110, values 0..19.
; value = 4*mode + (depth-1). One aligned store publishes both fields.
; The high 27-bit tag makes uninitialized/ordinary RAM decode as off.
; The address itself remains unresolved until dedicated RAM is proved safe.
define i32 @rd6_apply_scatter_cc(ptr %config, i32 %controller,
                                 i32 %value) nounwind {
entry:
  %cc = icmp eq i32 %controller, 110
  %range0 = icmp ult i32 %value, 28
  %below = icmp ult i32 %value, 12
  %above = icmp uge i32 %value, 16
  %kept = or i1 %below,%above
  %range = and i1 %range0,%kept
  %valid = and i1 %cc, %range
  br i1 %valid, label %publish, label %ignore

publish:
  %tagged = or i32 3601182720, %value
  store volatile i32 %tagged, ptr %config, align 4
  ret i32 1

ignore:
  ret i32 0
}

; Return mode in bits 0..7, depth in bits 8..15. Invalid/unpublished
; configuration is off/depth-1 (0x0100), so a missing CC is inert.
define i32 @rd6_read_scatter_config(ptr %config) nounwind {
entry:
  %raw = load volatile i32, ptr %config, align 4
  %tag = and i32 %raw, 4294967264
  %tag_ok = icmp eq i32 %tag, 3601182720
  %value = and i32 %raw, 31
  %range0 = icmp ult i32 %value, 28
  %below = icmp ult i32 %value, 12
  %above = icmp uge i32 %value, 16
  %kept = or i1 %below,%above
  %range = and i1 %range0,%kept
  %valid = and i1 %tag_ok, %range
  br i1 %valid, label %decode, label %off

decode:
  %mode = lshr i32 %value, 2
  %depth_low = and i32 %value, 3
  %depth = add i32 %depth_low, 1
  %shifted_depth = shl i32 %depth, 8
  %packed = or i32 %mode, %shifted_depth
  ret i32 %packed

off:
  ret i32 256
}

; Return nine hit bits: bit 0 accent, bits 1..8 voices.
; The stock pattern has nine consecutive 16-bit lanes at offsets +4..+20.
define i32 @rd6_voice_bits(ptr readonly %pattern, i32 %source_step) nounwind {
entry:
  %valid = icmp ult i32 %source_step, 16
  br i1 %valid, label %loop, label %invalid

loop:
  %lane = phi i32 [ 0, %entry ], [ %next_lane, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %next_acc, %loop ]
  %lane_twice = shl i32 %lane, 1
  %offset = add i32 %lane_twice, 4
  %address = getelementptr i8, ptr %pattern, i32 %offset
  %raw = load i16, ptr %address, align 2
  %mask = zext i16 %raw to i32
  %step_bit = shl i32 1, %source_step
  %overlap = and i32 %mask, %step_bit
  %hit = icmp ne i32 %overlap, 0
  %lane_bit = shl i32 1, %lane
  %new_bit = select i1 %hit, i32 %lane_bit, i32 0
  %next_acc = or i32 %acc, %new_bit
  %next_lane = add i32 %lane, 1
  %done = icmp eq i32 %next_lane, 9
  br i1 %done, label %finish, label %loop

finish:
  ret i32 %next_acc

invalid:
  ret i32 0
}

; Translate hit bits to the GPIOC BOP set mask used by the stock dispatcher.
; Clap accent's additional behavior is intentionally outside this function.
define i32 @rd6_gpio_c_set(i32 %hits) nounwind {
entry:
  %accent = and i32 %hits, 1
  %bd = and i32 %hits, 2
  %sd = and i32 %hits, 4
  %lt = and i32 %hits, 8
  %ht = and i32 %hits, 16
  %clap = and i32 %hits, 64
  %oh = and i32 %hits, 128
  %ch = and i32 %hits, 256
  %acc_gpio = shl i32 %accent, 6
  %bd_gpio = shl i32 %bd, 12
  %sd_gpio = shl i32 %sd, 12
  %lt_gpio = shl i32 %lt, 12
  %ht_gpio = lshr i32 %ht, 4
  %clap_gpio = shl i32 %clap, 3
  %oh_gpio = lshr i32 %oh, 6
  %ch_gpio = lshr i32 %ch, 6
  %m0 = or i32 %acc_gpio, %bd_gpio
  %m1 = or i32 %sd_gpio, %lt_gpio
  %m2 = or i32 %ht_gpio, %clap_gpio
  %m3 = or i32 %oh_gpio, %ch_gpio
  %m4 = or i32 %m0, %m1
  %m5 = or i32 %m2, %m3
  %result = or i32 %m4, %m5
  ret i32 %result
}

; Cymbal is the only voice in the stock dispatcher using GPIOB BOP.
define i32 @rd6_gpio_b_set(i32 %hits) nounwind {
entry:
  %cy = and i32 %hits, 32
  %result = shl i32 %cy, 10
  ret i32 %result
}

; Analog-only extra-hit filter for the TIMER14 emitter. The stock clap paths
; move GPIOB PB2 (accented: set; unaccented with PB2 high: clear) and then
; spend 200 iterations in the calibrated delay 0x08003196 (about 22,800
; interpreted instructions) before the clap trigger. That busy wait must not
; run inside TIMER14, so an extra hit whose clap would need it drops the clap
; bit and keeps its other voices; a clap that needs no pre-pulse (unaccented
; with PB2 low) is kept. Returns 0 when no voice remains, so the caller skips
; the emitter. The MIDI-capable research bridge keeps the stock pre-pulse.
define i32 @rd6_analog_only_hits(i32 %hits, i32 %pb2_high) nounwind {
entry:
  %clapbit = and i32 %hits, 64
  %clap = icmp ne i32 %clapbit, 0
  %accentbit = and i32 %hits, 1
  %accent = icmp ne i32 %accentbit, 0
  %pb2 = icmp ne i32 %pb2_high, 0
  %precondition = or i1 %accent, %pb2
  %needs_pre = and i1 %clap, %precondition
  %without_clap = and i32 %hits, 447
  %filtered = select i1 %needs_pre, i32 %without_clap, i32 %hits
  %voices = and i32 %filtered, 510
  %has_voice = icmp ne i32 %voices, 0
  %result = select i1 %has_voice, i32 %filtered, i32 0
  ret i32 %result
}

; Write a 40-byte shadow output frame. The caller applies this to hardware.
; u32 fields at offsets 0,4,8,12,16,20,24,28:
; C set, B set, C clear, B pre-action (0 none, 1 set, 2 clear), delay count, short counter,
; clap counter, MIDI note count. Bytes at +32..+39 are the queued note bytes.
define i32 @rd6_output_frame(i32 %hits, i32 %pb2_high, ptr %frame) nounwind {
entry:
  %cset = call i32 @rd6_gpio_c_set(i32 %hits)
  %bset = call i32 @rd6_gpio_b_set(i32 %hits)
  %accentbit = and i32 %hits, 1
  %accent = icmp ne i32 %accentbit, 0
  %clapbit = and i32 %hits, 64
  %clap = icmp ne i32 %clapbit, 0
  %pb2 = icmp ne i32 %pb2_high, 0
  %precondition = or i1 %accent, %pb2
  %pre = and i1 %clap, %precondition
  %prepolarity = select i1 %accent, i32 1, i32 2
  %bpre = select i1 %pre, i32 %prepolarity, i32 0
  %delay = select i1 %pre, i32 200, i32 0
  %cclear = select i1 %accent, i32 128, i32 192
  %shortbits = and i32 %hits, 446
  %anyshort = icmp ne i32 %shortbits, 0
  %shortcounter = select i1 %anyshort, i32 20, i32 4
  %clapcounter = select i1 %clap, i32 340, i32 0
  %f0 = getelementptr i32, ptr %frame, i32 0
  %f1 = getelementptr i32, ptr %frame, i32 1
  %f2 = getelementptr i32, ptr %frame, i32 2
  %f3 = getelementptr i32, ptr %frame, i32 3
  %f4 = getelementptr i32, ptr %frame, i32 4
  %f5 = getelementptr i32, ptr %frame, i32 5
  %f6 = getelementptr i32, ptr %frame, i32 6
  %f7 = getelementptr i32, ptr %frame, i32 7
  store i32 %cset, ptr %f0, align 4
  store i32 %bset, ptr %f1, align 4
  store i32 %cclear, ptr %f2, align 4
  store i32 %bpre, ptr %f3, align 4
  store i32 %delay, ptr %f4, align 4
  store i32 %shortcounter, ptr %f5, align 4
  store i32 %clapcounter, ptr %f6, align 4
  br label %loop

loop:
  %lane = phi i32 [ 0, %entry ], [ %nextlane, %advance ]
  %count = phi i32 [ 0, %entry ], [ %nextcount, %advance ]
  %bitptr = getelementptr [8 x i32], ptr @rd6_note_bits, i32 0, i32 %lane
  %bit = load i32, ptr %bitptr, align 4
  %overlap = and i32 %hits, %bit
  %hit = icmp ne i32 %overlap, 0
  br i1 %hit, label %emit, label %advance

emit:
  %noteptr = getelementptr [8 x i8], ptr @rd6_note_numbers, i32 0, i32 %lane
  %note = load i8, ptr %noteptr, align 1
  %accentbyte = select i1 %accent, i8 -128, i8 0
  %value = or i8 %note, %accentbyte
  %bytes = getelementptr i8, ptr %frame, i32 32
  %destination = getelementptr i8, ptr %bytes, i32 %count
  store i8 %value, ptr %destination, align 1
  br label %advance

advance:
  %increment = zext i1 %hit to i32
  %nextcount = add i32 %count, %increment
  %nextlane = add i32 %lane, 1
  %done = icmp eq i32 %nextlane, 8
  br i1 %done, label %finish, label %loop

finish:
  store i32 %nextcount, ptr %f7, align 4
  ret i32 %nextcount
}

; Apply a frame through caller-provided callbacks. Nothing is written to
; peripheral addresses directly, so the same function can run against a mock.
; write_cb(ctx, address, value), queue_cb(ctx, byte), delay_cb(ctx, count).
; The last three pointers address the stock short counter, clap counter,
; and short-voice flag respectively. The callback can use the actual GD32
; GPIO registers when a complete firmware bridge is eventually linked.
define void @rd6_apply_frame(ptr readonly %frame, ptr %ctx,
                             ptr %write_cb, ptr %queue_cb, ptr %delay_cb,
                             ptr %short_counter_ptr, ptr %clap_counter_ptr,
                             ptr %short_flag_ptr) nounwind {
entry:
  %cset_ptr = getelementptr i32, ptr %frame, i32 0
  %bpre_ptr = getelementptr i32, ptr %frame, i32 3
  %delay_ptr = getelementptr i32, ptr %frame, i32 4
  %short_ptr = getelementptr i32, ptr %frame, i32 5
  %clap_ptr = getelementptr i32, ptr %frame, i32 6
  %cset = load i32, ptr %cset_ptr, align 4
  %short = load i32, ptr %short_ptr, align 4
  %clap = load i32, ptr %clap_ptr, align 4
  call void %write_cb(ptr %ctx, i32 1207961640, i32 128)
  %accentmask = and i32 %cset, 64
  %accent = icmp ne i32 %accentmask, 0
  br i1 %accent, label %accent_set, label %accent_clear

accent_set:
  call void %write_cb(ptr %ctx, i32 1207961624, i32 64)
  br label %voices

accent_clear:
  call void %write_cb(ptr %ctx, i32 1207961640, i32 64)
  br label %voices

voices:
  %lane = phi i32 [ 0, %accent_set ], [ 0, %accent_clear ],
                   [ %nextlane, %advance ]
  %noteindex = phi i32 [ 0, %accent_set ], [ 0, %accent_clear ],
                        [ %nextindex, %advance ]
  %bitptr = getelementptr [8 x i32], ptr @rd6_note_bits, i32 0, i32 %lane
  %bit = load i32, ptr %bitptr, align 4
  %candidates = and i32 %cset, 512
  %isclaplane = icmp eq i32 %lane, 7
  %isclaphit = icmp ne i32 %candidates, 0
  %claphit = and i1 %isclaplane, %isclaphit
  %value_ptr = getelementptr [8 x i32], ptr @rd6_io_value, i32 0, i32 %lane
  %gpio_value = load i32, ptr %value_ptr, align 4
  %hit = icmp ne i32 %clap, 0
  %frame_cset = and i32 %cset, %gpio_value
  %c_hit = icmp ne i32 %frame_cset, 0
  ; Cymbal is on GPIOB, so use the clap/voice hit bit table below.
  %note_count_ptr = getelementptr i32, ptr %frame, i32 7
  %note_count = load i32, ptr %note_count_ptr, align 4
  %below_count = icmp ult i32 %noteindex, %note_count
  %note_bytes = getelementptr i8, ptr %frame, i32 32
  %note_ptr = getelementptr i8, ptr %note_bytes, i32 %noteindex
  %note_byte = load i8, ptr %note_ptr, align 1
  %note_masked = and i8 %note_byte, 127
  %expected_ptr = getelementptr [8 x i8], ptr @rd6_note_numbers, i32 0, i32 %lane
  %expected_note = load i8, ptr %expected_ptr, align 1
  %matches = icmp eq i8 %note_masked, %expected_note
  %present = and i1 %below_count, %matches
  br i1 %present, label %precheck, label %advance

precheck:
  br i1 %isclaplane, label %clap_pre, label %write_voice

clap_pre:
  %bpre = load i32, ptr %bpre_ptr, align 4
  %do_pre = icmp ne i32 %bpre, 0
  br i1 %do_pre, label %clap_pre_write, label %write_voice

clap_pre_write:
  %pre_set = icmp eq i32 %bpre, 1
  %pre_address = select i1 %pre_set, i32 1207960600, i32 1207960616
  call void %write_cb(ptr %ctx, i32 %pre_address, i32 4)
  %wait = load i32, ptr %delay_ptr, align 4
  call void %delay_cb(ptr %ctx, i32 %wait)
  br label %write_voice

write_voice:
  %address_ptr = getelementptr [8 x i32], ptr @rd6_io_address, i32 0, i32 %lane
  %address = load i32, ptr %address_ptr, align 4
  call void %write_cb(ptr %ctx, i32 %address, i32 %gpio_value)
  %note_wide = zext i8 %note_byte to i32
  call void %queue_cb(ptr %ctx, i32 %note_wide)
  br label %advance

advance:
  %increment = zext i1 %present to i32
  %nextindex = add i32 %noteindex, %increment
  %nextlane = add i32 %lane, 1
  %done = icmp eq i32 %nextlane, 8
  br i1 %done, label %finish, label %voices

finish:
  %short_active = icmp eq i32 %short, 20
  %flag = zext i1 %short_active to i32
  store i32 %flag, ptr %short_flag_ptr, align 4
  %clap_active = icmp ne i32 %clap, 0
  br i1 %clap_active, label %store_clap, label %store_short

store_clap:
  store i32 %clap, ptr %clap_counter_ptr, align 4
  br label %store_short

store_short:
  store i32 %short, ptr %short_counter_ptr, align 4
  ret void
}

; Called at each TIMER14 update. Caller advances next_index only on true.
; Minimum low gap must be included in gate_ticks by the caller.
; Every repeat, including the last, must end its gate (gate_ticks after it
; fires) at least a tempo-slack margin before the predicted next regular step,
; which is step_ticks (the measured previous step) after the arm. The margin
; is step_ticks/8: a next step that arrives up to 12.5 % early still finds the
; previous repeat's trigger line cleared, and one eighth is the largest
; power-of-two fraction that leaves the third repeat of a four-way ratchet
; possible (3/4 + 1/8 < 1). With the 18-update gate and the integer
; divisions below, a two-way ratchet keeps its repeat from 45 updates per
; step upward and a four-way ratchet keeps its third repeat for every step of
; 137 updates or more (and for 123, 126, 127, 130, 131 and 133 to 135, where
; the floored targets fall early); the first two repeats need 76 updates, as
; before. A repeat that cannot keep the margin is withheld, and so are any
; later repeats of that step. Tempo jumps larger than the margin are not
; covered: the stock regular hit then reloads the short counter while its
; trigger line is still high.
define i32 @rd6_ratchet_due(i32 %elapsed, i32 %step_ticks,
                             i32 %repeats, i32 %next_index,
                             i32 %gate_ticks) nounwind {
entry:
  %two = icmp eq i32 %repeats, 2
  %four = icmp eq i32 %repeats, 4
  %repok = or i1 %two, %four
  %indexlo = icmp uge i32 %next_index, 1
  %indexhi = icmp ult i32 %next_index, %repeats
  %valid_index = and i1 %indexlo, %indexhi
  %valid = and i1 %repok, %valid_index
  br i1 %valid, label %calculate, label %no

calculate:
  %spacing = udiv i32 %step_ticks, %repeats
  %enough = icmp ugt i32 %spacing, %gate_ticks
  %target = mul i32 %spacing, %next_index
  %reached = icmp uge i32 %elapsed, %target
  %pending = and i1 %enough, %reached
  br i1 %pending, label %margin, label %no

margin:
  ; With a nonzero gate_ticks this also keeps elapsed below step_ticks.
  %slack = lshr i32 %step_ticks, 3
  %gate_end0 = add i32 %elapsed, %gate_ticks
  %gate_end = add i32 %gate_end0, %slack
  %clear = icmp ule i32 %gate_end, %step_ticks
  %result = zext i1 %clear to i32
  ret i32 %result

no:
  ret i32 0
}

; Caller-owned state: eight consecutive u32 values in this order:
; elapsed, step_ticks, source_step, repeats, next_index, gate_ticks,
; transport_step, pattern_length. Only this state is written. This function
; stores repeats as 1, 2 or 4; 0 is the stop marker of rd6_guarded_timer_tick.
; Called once after a real sequencer step boundary. The returned hit bits are
; the voices for that regular step; the caller decides how to emit them.
define i32 @rd6_step_event(ptr %state, ptr readonly %pattern,
                           i32 %transport_step, i32 %length,
                           i32 %measured_ticks, i32 %mode,
                           i32 %depth, i32 %gate_ticks) nounwind {
entry:
  %source = call i32 @rd6_direction_snapshot(i32 %transport_step, i32 %length,
                                      i32 %mode, i32 %depth)
  %hits = call i32 @rd6_voice_bits(ptr %pattern, i32 %source)
  %ratchet = icmp eq i32 %mode, 4
  %has_duration = icmp ugt i32 %measured_ticks, 0
  %r1 = and i1 %ratchet, %has_duration
  %deep = icmp ugt i32 %depth, 2
  %count = select i1 %deep, i32 4, i32 2
  %repeats = select i1 %r1, i32 %count, i32 1
  %p0 = getelementptr i32, ptr %state, i32 0
  %p1 = getelementptr i32, ptr %state, i32 1
  %p2 = getelementptr i32, ptr %state, i32 2
  %p3 = getelementptr i32, ptr %state, i32 3
  %p4 = getelementptr i32, ptr %state, i32 4
  %p5 = getelementptr i32, ptr %state, i32 5
  %p6 = getelementptr i32, ptr %state, i32 6
  %p7 = getelementptr i32, ptr %state, i32 7
  store i32 0, ptr %p0, align 4
  store i32 %measured_ticks, ptr %p1, align 4
  store i32 %source, ptr %p2, align 4
  store i32 %repeats, ptr %p3, align 4
  store i32 1, ptr %p4, align 4
  store i32 %gate_ticks, ptr %p5, align 4
  store i32 %transport_step, ptr %p6, align 4
  store i32 %length, ptr %p7, align 4
  ret i32 %hits
}

; Called once per TIMER14 update after stock pulse maintenance.
; clap_counter is the stock 0x2000119C countdown. A busy clap is suppressed;
; its independent 340-tick sequence cannot be treated as a short trigger.
define i32 @rd6_tick_event(ptr %state, ptr readonly %pattern,
                           i32 %clap_counter) nounwind {
entry:
  %p0 = getelementptr i32, ptr %state, i32 0
  %p1 = getelementptr i32, ptr %state, i32 1
  %p2 = getelementptr i32, ptr %state, i32 2
  %p3 = getelementptr i32, ptr %state, i32 3
  %p4 = getelementptr i32, ptr %state, i32 4
  %p5 = getelementptr i32, ptr %state, i32 5
  %old = load i32, ptr %p0, align 4
  %elapsed = add i32 %old, 1
  store i32 %elapsed, ptr %p0, align 4
  %config = load volatile i32, ptr inttoptr (i32 536879104 to ptr), align 4
  %tag = and i32 %config, 4294967264
  %tag_ok = icmp eq i32 %tag, 3601182720
  %value = and i32 %config, 31
  %lo = icmp uge i32 %value, 16
  %hi = icmp ule i32 %value, 19
  %range_ok = and i1 %lo, %hi
  %enabled = and i1 %tag_ok, %range_ok
  br i1 %enabled, label %active, label %released
released:
  store i32 1, ptr %p3, align 4
  ret i32 0
active:
  %step_ticks = load i32, ptr %p1, align 4
  %repeats = load i32, ptr %p3, align 4
  %next_index = load i32, ptr %p4, align 4
  %gate_ticks = load i32, ptr %p5, align 4
  %due = call i32 @rd6_ratchet_due(i32 %elapsed, i32 %step_ticks,
                                   i32 %repeats, i32 %next_index,
                                   i32 %gate_ticks)
  %is_due = icmp ne i32 %due, 0
  br i1 %is_due, label %fire, label %quiet

fire:
  %next = add i32 %next_index, 1
  store i32 %next, ptr %p4, align 4
  %source = load i32, ptr %p2, align 4
  %hits = call i32 @rd6_voice_bits(ptr %pattern, i32 %source)
  %clap_busy = icmp ne i32 %clap_counter, 0
  %without_clap = and i32 %hits, 447
  %filtered = select i1 %clap_busy, i32 %without_clap, i32 %hits
  %voices = and i32 %filtered, 510
  %has_voice = icmp ne i32 %voices, 0
  %result = select i1 %has_voice, i32 %filtered, i32 0
  ret i32 %result

quiet:
  ret i32 0
}

; TIMER14 may preempt TIMER13 after the stock transport step is advanced but
; before the later voice-dispatch hook publishes its command. In that window,
; suppress an old-step ratchet instead of firing across the new step boundary.
; This guard assumes the observed TIMER14-above-TIMER13 priority persists.
; transport addresses the stock structure at 0x20000BB4: +0 is the playing
; word, +8 the step. While the playing word is 0 (after either stop form, or
; before a start) nothing fires: the guard marks the published command as
; consumed (last_command = command) and sets the repeats word to 0, a value
; rd6_step_event and the invalid path never store, so a pending repeat is
; dropped at the stop. A start sets the playing word before step 0 is
; published (internal start) or long before the first external clock
; (external arm); in that gap a matching old command only ticks, because
; rd6_ratchet_due rejects 0 repeats. The next publication then arms without a
; measured duration (see rd6_timer_owned_tick): the first step after a start
; plays its regular hit without repeats, like the step after a missed command.
define i32 @rd6_guarded_timer_tick(ptr %state, ptr %command,
                                   ptr readonly %pattern,
                                   i32 %clap_counter, i32 %gate_ticks,
                                   ptr %transport) nounwind {
entry:
  %playing = load volatile i32, ptr %transport, align 4
  %published = load volatile i32, ptr %command, align 4
  %stopped = icmp eq i32 %playing, 0
  br i1 %stopped, label %stop, label %running

stop:
  %p3 = getelementptr i32, ptr %state, i32 3
  store i32 0, ptr %p3, align 4
  %p8 = getelementptr i32, ptr %state, i32 8
  store i32 %published, ptr %p8, align 4
  ret i32 0

running:
  %command_step = and i32 %published, 31
  %step_ptr = getelementptr i32, ptr %transport, i32 2
  %step = load volatile i32, ptr %step_ptr, align 4
  %matches = icmp eq i32 %command_step, %step
  br i1 %matches, label %tick, label %skip

tick:
  %hits = call i32 @rd6_timer_owned_tick(
    ptr %state, ptr %command, ptr %pattern,
    i32 %clap_counter, i32 %gate_ticks)
  ret i32 %hits

skip:
  ret i32 0
}

; Single-writer handoff: the step hook publishes one aligned 32-bit command.
; Bits 0..4=step, 5..9=length, 10..12=mode, 13..15=depth,
; 16..31=nonzero sequence. The TIMER14 hook alone writes the nine-word state.
; This avoids a timer interrupt observing a partly initialized step state.
define i32 @rd6_publish_step_command(ptr %command, i32 %step,
                                     i32 %length, i32 %mode,
                                     i32 %depth) nounwind {
entry:
  %old = load volatile i32, ptr %command, align 4
  %old_seq = lshr i32 %old, 16
  %increment = add i32 %old_seq, 1
  %wrapped = and i32 %increment, 65535
  %zero = icmp eq i32 %wrapped, 0
  %seq = select i1 %zero, i32 1, i32 %wrapped
  %s = and i32 %step, 31
  %l0 = and i32 %length, 31
  %l = shl i32 %l0, 5
  %m0 = and i32 %mode, 7
  %m = shl i32 %m0, 10
  %d0 = and i32 %depth, 7
  %d = shl i32 %d0, 13
  %q = shl i32 %seq, 16
  %a = or i32 %s, %l
  %b = or i32 %a, %m
  %c = or i32 %b, %d
  %packed = or i32 %c, %q
  store volatile i32 %packed, ptr %command, align 4
  ret i32 %packed
}

; state points to nine u32 words: the original eight, then last_command.
; Only TIMER14 calls this function. Step boundaries are detected from the
; published command, and the prior TIMER14 tick count estimates step length.
; A missed command disables ratchets for one step rather than using a stale
; duration, and so does a stop: rd6_guarded_timer_tick leaves the repeats word
; at 0 while the transport is stopped, so the interval to the next
; publication, which spans the stop, is not used either. The stock regular
; hit is emitted by its original dispatcher.
define i32 @rd6_timer_owned_tick(ptr %state, ptr %command,
                                 ptr readonly %pattern, i32 %clap_counter,
                                 i32 %gate_ticks) nounwind {
entry:
  %published = load volatile i32, ptr %command, align 4
  %seq = lshr i32 %published, 16
  %active = icmp ne i32 %seq, 0
  br i1 %active, label %inspect, label %quiet

inspect:
  %p8 = getelementptr i32, ptr %state, i32 8
  %last = load i32, ptr %p8, align 4
  %same = icmp eq i32 %published, %last
  br i1 %same, label %tick, label %new_step

new_step:
  %last_seq = lshr i32 %last, 16
  %increment = add i32 %last_seq, 1
  %wrapped = and i32 %increment, 65535
  %wrap_zero = icmp eq i32 %wrapped, 0
  %expected = select i1 %wrap_zero, i32 1, i32 %wrapped
  %ordered = icmp eq i32 %seq, %expected
  %not_first = icmp ne i32 %last, 0
  %p3 = getelementptr i32, ptr %state, i32 3
  %armed_repeats = load i32, ptr %p3, align 4
  %not_stopped = icmp ne i32 %armed_repeats, 0
  %linked = and i1 %ordered, %not_first
  %contiguous = and i1 %linked, %not_stopped
  %p0 = getelementptr i32, ptr %state, i32 0
  %elapsed = load i32, ptr %p0, align 4
  ; The publication is consumed on one TIMER14 update; count that update
  ; when estimating the previous step's duration, then arm without ticking.
  %elapsed_with_boundary = add i32 %elapsed, 1
  %duration = select i1 %contiguous, i32 %elapsed_with_boundary, i32 0
  %step = and i32 %published, 31
  %length_shift = lshr i32 %published, 5
  %length = and i32 %length_shift, 31
  %mode_shift = lshr i32 %published, 10
  %mode = and i32 %mode_shift, 7
  %depth_shift = lshr i32 %published, 13
  %depth = and i32 %depth_shift, 7
  %len_lo = icmp uge i32 %length, 2
  %len_hi = icmp ule i32 %length, 16
  %step_ok = icmp ult i32 %step, %length
  %mode_ok = icmp ule i32 %mode, 6
  %depth_lo = icmp uge i32 %depth, 1
  %depth_hi = icmp ule i32 %depth, 4
  %v0 = and i1 %len_lo, %len_hi
  %v1 = and i1 %step_ok, %mode_ok
  %v2 = and i1 %depth_lo, %depth_hi
  %v3 = and i1 %v0, %v1
  %valid = and i1 %v3, %v2
  br i1 %valid, label %arm, label %invalid

arm:
  %discard_regular_hit = call i32 @rd6_step_event(
    ptr %state, ptr %pattern, i32 %step, i32 %length,
    i32 %duration, i32 %mode, i32 %depth, i32 %gate_ticks)
  store i32 %published, ptr %p8, align 4
  ret i32 0

invalid:
  store i32 %published, ptr %p8, align 4
  store i32 0, ptr %p0, align 4
  store i32 1, ptr %p3, align 4
  ret i32 0

tick:
  %hits = call i32 @rd6_tick_event(ptr %state, ptr %pattern,
                                   i32 %clap_counter)
  %current = load volatile i32, ptr %command, align 4
  %still_current = icmp eq i32 %current, %published
  %result = select i1 %still_current, i32 %hits, i32 0
  ret i32 %result

quiet:
  ret i32 0
}

; TEST05 capture roll. Pattern clock continues; the stock dispatcher is
; silenced during roll. TIMER14 owns roll state except the aligned last-hit
; word, written by the step hook. No EEPROM, MIDI queue, GPIO or delay here.
; Roll state 0x20002048: active, captured_hits, phase, duration, cooldown,
; last_nonempty_hits. Startup initializes the complete 96-byte allocation.

define i32 @rd6_capture_source_mask(i32 %step, i32 %length, i32 %mode,
                            i32 %depth, i32 %stock_mask) nounwind {
entry:
  %lo = icmp uge i32 %mode, 5
  %hi = icmp ule i32 %mode, 6
  %roll = and i1 %lo, %hi
  br i1 %roll, label %silence, label %normal
silence:
  ret i32 0
normal:
  %mask = call i32 @rd6_legacy_source_mask(i32 %step, i32 %length, i32 %mode, i32 %depth, i32 %stock_mask)
  %source = call i32 @rd6_source_step(i32 %step, i32 %length, i32 %mode, i32 %depth)
  %hits = call i32 @rd6_voice_bits(ptr inttoptr (i32 536873628 to ptr), i32 %source)
  %voices = and i32 %hits, 510
  %hasvoices = icmp ne i32 %voices, 0
  %audible = icmp ne i32 %mask, 0
  %nonempty = and i1 %hasvoices,%audible
  br i1 %nonempty, label %remember, label %done
remember:
  ; One aligned store. The timer captures either complete old or new chord.
  store volatile i32 %hits, ptr inttoptr (i32 536879196 to ptr), align 4
  br label %done
done:
  ret i32 %mask
}

define i32 @rd6_roll_guarded_tick(ptr %state, ptr %command,
    ptr %pattern, i32 %clap, i32 %gate, ptr %transport) nounwind {
entry:
  call void @rd6_direction_transport_check(ptr %transport)
  ; Keep TEST04's handoff, elapsed duration measurement and stop guard alive.
  %legacy = call i32 @rd6_guarded_timer_tick(ptr %state, ptr %command,
    ptr %pattern, i32 %clap, i32 %gate, ptr %transport)
  %activep = inttoptr i32 536879176 to ptr
  %hitsp = getelementptr i32, ptr %activep, i32 1
  %phasep = getelementptr i32, ptr %activep, i32 2
  %durationp = getelementptr i32, ptr %activep, i32 3
  %coolp = getelementptr i32, ptr %activep, i32 4
  %lastp = getelementptr i32, ptr %activep, i32 5
  %cool = load i32, ptr %coolp, align 4
  %coolzero = icmp eq i32 %cool, 0
  %cooldec = sub i32 %cool, 1
  %coolnow = select i1 %coolzero, i32 0, i32 %cooldec
  store i32 %coolnow, ptr %coolp, align 4
  %packed = call i32 @rd6_read_scatter_config(ptr inttoptr (i32 536879104 to ptr))
  %mode = and i32 %packed, 255
  %depth = lshr i32 %packed, 8
  %mlo = icmp uge i32 %mode, 5
  %mhi = icmp ule i32 %mode, 6
  %roll = and i1 %mlo, %mhi
  %playing = load volatile i32, ptr %transport, align 4
  %running = icmp ne i32 %playing, 0
  %selector = load volatile i8, ptr inttoptr (i32 536871520 to ptr), align 1
  %patternplay = icmp eq i8 %selector, 2
  %runroll = and i1 %roll, %running
  %enabled = and i1 %runroll, %patternplay
  br i1 %enabled, label %held, label %release
release:
  store i32 0, ptr %activep, align 4
  store i32 0, ptr %phasep, align 4
  store i32 0, ptr %durationp, align 4
  br i1 %running, label %released, label %clear_last
clear_last:
  store volatile i32 0, ptr %lastp, align 4
  br label %released
released:
  ret i32 %legacy
held:
  %active = load i32, ptr %activep, align 4
  %fresh = icmp eq i32 %active, 0
  br i1 %fresh, label %capture, label %timing
capture:
  %last = load volatile i32, ptr %lastp, align 4
  store i32 %last, ptr %hitsp, align 4
  store i32 1, ptr %activep, align 4
  store i32 0, ptr %phasep, align 4
  store i32 0, ptr %durationp, align 4
  br label %timing
timing:
  %stepp = getelementptr i32, ptr %state, i32 1
  %duration = load i32, ptr %stepp, align 4
  %dlo = icmp ugt i32 %duration, 0
  %dhi = icmp ule i32 %duration, 16384
  %valid = and i1 %dlo, %dhi
  br i1 %valid, label %advance, label %wait
wait:
  store i32 0, ptr %phasep, align 4
  store i32 0, ptr %durationp, align 4
  ret i32 0
advance:
  ; phase/4D is the fractional roll cycle; rescale on measured tempo change.
  ; D <=16384 and phase<4D bounds phase*newD below 2^30 (no overflow).
  %old = load i32, ptr %phasep, align 4
  %previous = load i32, ptr %durationp, align 4
  %pzero = icmp eq i32 %previous, 0
  %safe = select i1 %pzero, i32 1, i32 %previous
  %product = mul i32 %old, %duration
  %scaled = udiv i32 %product, %safe
  %phase = select i1 %pzero, i32 0, i32 %scaled
  %deep = icmp ugt i32 %depth, 3
  %rate = select i1 %deep, i32 3, i32 %depth
  %power = shl i32 1, %rate
  %triplet = icmp eq i32 %mode, 6
  %half = lshr i32 %power, 1
  %trirate = add i32 %power, %half
  %increment = select i1 %triplet, i32 %trirate, i32 %power
  %next = add i32 %phase, %increment
  %threshold = shl i32 %duration, 2
  %due = icmp uge i32 %next, %threshold
  ; Modulo skips missed subdivisions instead of generating catch-up bursts.
  %wrapped = urem i32 %next, %threshold
  store i32 %wrapped, ptr %phasep, align 4
  store i32 %duration, ptr %durationp, align 4
  %ready = icmp eq i32 %coolnow, 0
  %scheduled = and i1 %due, %ready
  br i1 %scheduled, label %gatecheck, label %quiet
gatecheck:
  %short = load volatile i32, ptr inttoptr (i32 536875416 to ptr), align 4
  %gateclear = icmp ule i32 %short, 4
  br i1 %gateclear, label %fire, label %quiet
fire:
  %hits = load i32, ptr %hitsp, align 4
  %busy = icmp ne i32 %clap, 0
  %without = and i32 %hits, 447
  %filtered = select i1 %busy, i32 %without, i32 %hits
  %voices = and i32 %filtered, 510
  %audible = icmp ne i32 %voices, 0
  %answer = select i1 %audible, i32 %filtered, i32 0
  ; A fixed 32-update retrigger gap also protects immediate off/on gestures.
  store i32 32, ptr %coolp, align 4
  ret i32 %answer
quiet:
  ret i32 0
}

; TEST06 direction layer. Stock transport/clock are never written.
; Main panel writes cfg; step hook owns phase/length/seed/snapshot/initialized.
; Timer clears the direction allocation only while stopped/outside Pattern Play.
; 0x20002060: cfg(0forward/1reverse/2random/3pingpong), next_phase,
; previous_length, random_seed, snapshot, initialized. All startup-zeroed.

define i32 @rd6_direction_source(i32 %step,i32 %length) nounwind {
entry:
  %cfgp = inttoptr i32 536879200 to ptr
  %phasep = getelementptr i32, ptr %cfgp, i32 1
  %lengthp = getelementptr i32, ptr %cfgp, i32 2
  %seedp = getelementptr i32, ptr %cfgp, i32 3
  %initp = getelementptr i32, ptr %cfgp, i32 5
  %d0 = load volatile i32, ptr %cfgp, align 4
  %dok = icmp ule i32 %d0,3
  %requested = select i1 %dok,i32 %d0,i32 0
  ; Only Reverse is queued. Other directions apply on the next regular tick.
  ; Current effective direction continues through the remainder of this bar.
  %activep = inttoptr i32 536879224 to ptr
  %previous_active = load volatile i32,ptr %activep,align 4
  %is_reverse_request = icmp eq i32 %requested,1
  %at_bar_start = icmp eq i32 %step,0
  %reverse_choice = select i1 %at_bar_start,i32 1,i32 %previous_active
  %direction = select i1 %is_reverse_request,i32 %reverse_choice,i32 %requested
  store volatile i32 %direction,ptr %activep,align 4
  %oldlength = load i32,ptr %lengthp,align 4
  %oldphase = load i32,ptr %phasep,align 4
  %initialized = load i32,ptr %initp,align 4
  %last = sub i32 %length,1
  %period = shl i32 %last,1
  %same = icmp eq i32 %oldlength,%length
  %started = icmp ne i32 %initialized,0
  %existing = and i1 %same,%started
  %p0 = select i1 %existing,i32 %oldphase,i32 %step
  %phase = urem i32 %p0,%period
  %next0 = add i32 %phase,1
  %next = urem i32 %next0,%period
  store i32 %next,ptr %phasep,align 4
  store i32 %length,ptr %lengthp,align 4
  store i32 1,ptr %initp,align 4
  %oldseed = load i32,ptr %seedp,align 4
  %empty = icmp eq i32 %oldseed,0
  %seed = select i1 %empty,i32 1831565813,i32 %oldseed
  %a = shl i32 %seed,13
  %b = xor i32 %seed,%a
  %c = lshr i32 %b,17
  %d = xor i32 %b,%c
  %e = shl i32 %d,5
  %randomseed = xor i32 %d,%e
  store i32 %randomseed,ptr %seedp,align 4
  %random = urem i32 %randomseed,%length
  %reverse = sub i32 %last,%step
  %up = icmp ult i32 %phase,%length
  %down = sub i32 %period,%phase
  %pingpong = select i1 %up,i32 %phase,i32 %down
  %rev = icmp eq i32 %direction,1
  %rnd = icmp eq i32 %direction,2
  %ping = icmp eq i32 %direction,3
  %s0 = select i1 %rev,i32 %reverse,i32 %step
  %s1 = select i1 %rnd,i32 %random,i32 %s0
  %source = select i1 %ping,i32 %pingpong,i32 %s1
  ret i32 %source
}

define i32 @rd6_source_mask(i32 %step,i32 %length,i32 %mode,i32 %depth,i32 %stock_mask) nounwind {
entry:
  %lo = icmp uge i32 %length,2
  %hi = icmp ule i32 %length,16
  %sok = icmp ult i32 %step,%length
  %lvalid = and i1 %lo,%hi
  %valid = and i1 %lvalid,%sok
  br i1 %valid,label %map,label %fallback
fallback:
  ret i32 %stock_mask
map:
  %directed = call i32 @rd6_direction_source(i32 %step,i32 %length)
  %direction = load volatile i32,ptr inttoptr (i32 536879200 to ptr),align 4
  %dlo = icmp uge i32 %direction,1
  %dhi = icmp ule i32 %direction,3
  %enabled = and i1 %dlo,%dhi
  %directmask = shl i32 1,%directed
  %fallbackmask = select i1 %enabled,i32 %directmask,i32 %stock_mask
  %mask = call i32 @rd6_capture_source_mask(i32 %directed,i32 %length,i32 %mode,i32 %depth,i32 %fallbackmask)
  %source = call i32 @rd6_source_step(i32 %directed,i32 %length,i32 %mode,i32 %depth)
  ; Publish one complete choice for TIMER14. Random never re-rolls in the timer.
  %a = shl i32 %length,5
  %b = shl i32 %source,10
  %c = or i32 %step,%a
  %d = or i32 %c,%b
  %snapshot = or i32 %d,3506438144
  store volatile i32 %snapshot,ptr inttoptr (i32 536879216 to ptr),align 4
  ret i32 %mask
}

define i32 @rd6_direction_snapshot(i32 %step,i32 %length,i32 %mode,i32 %depth) nounwind {
entry:
  %snapshot = load volatile i32,ptr inttoptr (i32 536879216 to ptr),align 4
  %tag = and i32 %snapshot,4294934528
  %tagok = icmp eq i32 %tag,3506438144
  %s = and i32 %snapshot,31
  %ls = lshr i32 %snapshot,5
  %l = and i32 %ls,31
  %same = icmp eq i32 %s,%step
  %lengthok = icmp eq i32 %l,%length
  %sr = lshr i32 %snapshot,10
  %source = and i32 %sr,31
  %bound = icmp ult i32 %source,%length
  %v0 = and i1 %tagok,%same
  %v1 = and i1 %lengthok,%bound
  %valid = and i1 %v0,%v1
  br i1 %valid,label %chosen,label %fallback
chosen:
  ret i32 %source
fallback:
  %ordinary = call i32 @rd6_source_step(i32 %step,i32 %length,i32 %mode,i32 %depth)
  ret i32 %ordinary
}

define void @rd6_direction_transport_check(ptr %transport) nounwind {
entry:
  %playing = load volatile i32,ptr %transport,align 4
  %stopped = icmp eq i32 %playing,0
  %selector = load volatile i8,ptr inttoptr (i32 536871520 to ptr),align 1
  %other = icmp ne i8 %selector,2
  %reset = or i1 %stopped,%other
  br i1 %reset,label %clear,label %done
clear:
  store volatile i32 0,ptr inttoptr (i32 536879200 to ptr),align 4
  store i32 0,ptr inttoptr (i32 536879204 to ptr),align 4
  store i32 0,ptr inttoptr (i32 536879208 to ptr),align 4
  store i32 0,ptr inttoptr (i32 536879212 to ptr),align 4
  store volatile i32 0,ptr inttoptr (i32 536879216 to ptr),align 4
  store i32 0,ptr inttoptr (i32 536879220 to ptr),align 4
  store volatile i32 0,ptr inttoptr (i32 536879224 to ptr),align 4
  br label %done
done:
  ret void
}
