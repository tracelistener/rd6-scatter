target triple = "thumbv7em-none-eabi"
define void @rd6_status_emit() nounwind {
entry:
  %layerraw = load volatile i32, ptr inttoptr (i32 536879148 to ptr), align 4
  %layer = and i32 %layerraw, 127
  %directionraw = load volatile i32, ptr inttoptr (i32 536879200 to ptr), align 4
  %direction = and i32 %directionraw, 127
  %latchraw = load volatile i32, ptr inttoptr (i32 536879152 to ptr), align 4
  %latch = and i32 %latchraw, 127
  %selectionraw = load volatile i32, ptr inttoptr (i32 536879156 to ptr), align 4
  %selection = and i32 %selectionraw, 127
  %configraw = load volatile i32, ptr inttoptr (i32 536879104 to ptr), align 4
  %config = and i32 %configraw, 127
  %selectorraw = load volatile i8, ptr inttoptr (i32 536871520 to ptr), align 1
  %selector = zext i8 %selectorraw to i32
  %playingraw = load volatile i32, ptr inttoptr (i32 536873908 to ptr), align 4
  %playing = and i32 %playingraw, 127
  %snapshotraw = load volatile i32, ptr inttoptr (i32 536879216 to ptr), align 4
  %snapshot = and i32 %snapshotraw, 127
  %last_keyraw = load volatile i32, ptr inttoptr (i32 536879164 to ptr), align 4
  %last_key = and i32 %last_keyraw, 127
  %active0 = and i32 %configraw, 31
  %active = lshr i32 %active0, 2
  %clockstep = and i32 %snapshotraw, 31
  %source0 = lshr i32 %snapshotraw, 10
  %source = and i32 %source0, 31
  %tag = and i32 %snapshotraw, 4294934528
  %valid = icmp eq i32 %tag, 3506438144
  %valid32 = zext i1 %valid to i32
  %effective_raw = load volatile i32, ptr inttoptr (i32 536879224 to ptr), align 4
  %effective = and i32 %effective_raw,127
  %buffer = alloca [13 x i32], align 4
  %v0 = shl i32 12, 24
  %packet0 = or i32 %v0, 42506
  %p0 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 0
  store i32 %packet0, ptr %p0, align 4
  %v1 = shl i32 %layer, 24
  %packet1 = or i32 %v1, 108042
  %p1 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 1
  store i32 %packet1, ptr %p1, align 4
  %v2 = shl i32 %direction, 24
  %packet2 = or i32 %v2, 173578
  %p2 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 2
  store i32 %packet2, ptr %p2, align 4
  %v3 = shl i32 %latch, 24
  %packet3 = or i32 %v3, 239114
  %p3 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 3
  store i32 %packet3, ptr %p3, align 4
  %v4 = shl i32 %selection, 24
  %packet4 = or i32 %v4, 304650
  %p4 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 4
  store i32 %packet4, ptr %p4, align 4
  %v5 = shl i32 %active, 24
  %packet5 = or i32 %v5, 370186
  %p5 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 5
  store i32 %packet5, ptr %p5, align 4
  %v6 = shl i32 %selector, 24
  %packet6 = or i32 %v6, 435722
  %p6 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 6
  store i32 %packet6, ptr %p6, align 4
  %v7 = shl i32 %playing, 24
  %packet7 = or i32 %v7, 501258
  %p7 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 7
  store i32 %packet7, ptr %p7, align 4
  %v8 = shl i32 %clockstep, 24
  %packet8 = or i32 %v8, 566794
  %p8 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 8
  store i32 %packet8, ptr %p8, align 4
  %v9 = shl i32 %source, 24
  %packet9 = or i32 %v9, 632330
  %p9 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 9
  store i32 %packet9, ptr %p9, align 4
  %v10 = shl i32 %last_key, 24
  %packet10 = or i32 %v10, 697866
  %p10 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 10
  store i32 %packet10, ptr %p10, align 4
  %v11 = shl i32 %valid32, 24
  %packet11 = or i32 %v11, 763402
  %p11 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 11
  store i32 %packet11, ptr %p11, align 4
  %v12 = shl i32 %effective, 24
  %packet12 = or i32 %v12, 828938
  %p12 = getelementptr [13 x i32], ptr %buffer, i32 0, i32 12
  store i32 %packet12, ptr %p12, align 4
  call void inttoptr (i32 134249765 to ptr)(ptr %buffer, i32 52)
  ret void
}
define i32 @rd6_apply_with_status(ptr %config,i32 %cc,i32 %value) nounwind {
entry:
  %controller = icmp eq i32 %cc,112
  %request = icmp eq i32 %value,0
  %status = and i1 %controller,%request
  br i1 %status,label %report,label %legacy
report:
  call void @rd6_status_emit()
  ret i32 0
legacy:
  %result = call i32 inttoptr (i32 134268173 to ptr)(ptr %config,i32 %cc,i32 %value)
  ret i32 %result
}
