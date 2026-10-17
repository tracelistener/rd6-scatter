; ModuleID = "rd6_panel_controls"
target triple = "thumbv7em-none-eabi"
target datalayout = ""

define void @"rd6_panel_release_stock_step"(ptr %".1", ptr %".2", i32 %".3") nounwind optsize
{
entry:
  %".5" = getelementptr i8, ptr %".1", i32 224
  %".6" = sub i32 %".3", 3
  %".7" = getelementptr i32, ptr %".5", i32 %".6"
  store i32 0, ptr %".7"
  %".9" = alloca i32
  store i32 0, i32* %".9"
  br label %"loop"
loop:
  %".12" = phi  i32 [0, %"entry"], [%".20", %"loop"]
  %".13" = getelementptr i32, ptr %".5", i32 %".12"
  %".14" = load i32, ptr %".13"
  %".15" = icmp eq i32 %".14", 1
  %".16" = zext i1 %".15" to i32
  %".17" = load i32, i32* %".9"
  %".18" = or i32 %".17", %".16"
  store i32 %".18", i32* %".9"
  %".20" = add i32 %".12", 1
  %".21" = icmp ult i32 %".20", 16
  br i1 %".21", label %"loop", label %"done"
done:
  %".23" = load i32, i32* %".9"
  %".24" = getelementptr i8, ptr %".2", i32 4294967288
  store i32 %".23", ptr %".24"
  ret void
}

define void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".3", i32 %".4") nounwind optsize
{
entry:
  %".6" = mul i32 %".4", 8
  %".7" = getelementptr i8, ptr %".1", i32 %".6"
  %".8" = load i8, ptr %".7"
  %".9" = zext i8 %".8" to i32
  %".10" = icmp uge i32 %".9", 3
  br i1 %".10", label %"entry.if", label %"entry.endif"
entry.if:
  %".12" = mul i32 %".4", 8
  %".13" = getelementptr i8, ptr %".1", i32 %".12"
  store i8 7, ptr %".13"
  %".15" = getelementptr i32, ptr %".2", i32 6
  %".16" = load i32, ptr %".15"
  %".17" = shl i32 1, %".4"
  %".18" = or i32 %".16", %".17"
  %".19" = getelementptr i32, ptr %".2", i32 6
  store i32 %".18", ptr %".19"
  %".21" = icmp uge i32 %".4", 3
  %".22" = icmp ule i32 %".4", 18
  %".23" = and i1 %".21", %".22"
  br i1 %".23", label %"entry.if.if", label %"entry.if.endif"
entry.endif:
  %".35" = icmp eq i32 %".4", 2
  br i1 %".35", label %"entry.endif.if", label %"entry.endif.endif"
entry.if.if:
  %".25" = getelementptr i8, ptr %".1", i32 224
  %".26" = sub i32 %".4", 3
  %".27" = getelementptr i32, ptr %".25", i32 %".26"
  %".28" = load i32, ptr %".27"
  %".29" = icmp eq i32 %".28", 1
  br i1 %".29", label %"entry.if.if.if", label %"entry.if.if.endif"
entry.if.endif:
  br label %"entry.endif"
entry.if.if.if:
  call void @"rd6_panel_release_stock_step"(ptr %".1", ptr %".3", i32 %".4")
  br label %"entry.if.if.endif"
entry.if.if.endif:
  br label %"entry.if.endif"
entry.endif.if:
  store i32 0, ptr %".3"
  br label %"entry.endif.endif"
entry.endif.endif:
  ret void
}

define void @"rd6_panel_cleanup"(ptr %".1", ptr %".2") nounwind optsize
{
entry:
  br label %"loop"
loop:
  %".5" = phi  i32 [0, %"entry"], [%".33", %"loop.endif"]
  %".6" = shl i32 1, %".5"
  %".7" = getelementptr i32, ptr %".2", i32 6
  %".8" = load i32, ptr %".7"
  %".9" = and i32 %".8", %".6"
  %".10" = icmp ne i32 %".9", 0
  %".11" = mul i32 %".5", 8
  %".12" = getelementptr i8, ptr %".1", i32 %".11"
  %".13" = load i8, ptr %".12"
  %".14" = zext i8 %".13" to i32
  br i1 %".10", label %"loop.if", label %"loop.endif"
done:
  ret void
loop.if:
  %".16" = icmp ule i32 %".14", 1
  br i1 %".16", label %"loop.if.if", label %"loop.if.else"
loop.endif:
  %".33" = add i32 %".5", 1
  %".34" = icmp ult i32 %".33", 21
  br i1 %".34", label %"loop", label %"done"
loop.if.if:
  %".18" = mul i32 %".5", 8
  %".19" = getelementptr i8, ptr %".1", i32 %".18"
  store i8 0, ptr %".19"
  %".21" = getelementptr i32, ptr %".2", i32 6
  %".22" = load i32, ptr %".21"
  %".23" = xor i32 %".6", -1
  %".24" = and i32 %".22", %".23"
  %".25" = getelementptr i32, ptr %".2", i32 6
  store i32 %".24", ptr %".25"
  br label %"loop.if.endif"
loop.if.else:
  %".28" = mul i32 %".5", 8
  %".29" = getelementptr i8, ptr %".1", i32 %".28"
  store i8 7, ptr %".29"
  br label %"loop.if.endif"
loop.if.endif:
  br label %"loop.endif"
}

define void @"rd6_panel_publish"(ptr %".1", ptr %".2", i32 %".3") nounwind optsize
{
entry:
  %".5" = getelementptr i32, ptr %".1", i32 2
  %".6" = load i32, ptr %".5"
  %".7" = getelementptr i32, ptr %".1", i32 3
  %".8" = load i32, ptr %".7"
  %".9" = mul i32 %".6", 4
  %".10" = sub i32 %".8", 1
  %".11" = add i32 %".9", %".10"
  %".12" = icmp ne i32 %".3", 0
  %".13" = select  i1 %".12", i32 %".11", i32 0
  %".14" = or i32 %".13", 3601182720
  store i32 %".14", ptr %".2"
  %".16" = getelementptr i32, ptr %".1", i32 5
  store i32 1, ptr %".16"
  ret void
}

define void @"rd6_panel_cancel"(ptr %".1", ptr %".2") nounwind optsize
{
entry:
  %".4" = getelementptr i32, ptr %".1", i32 5
  %".5" = load i32, ptr %".4"
  %".6" = icmp ne i32 %".5", 0
  br i1 %".6", label %"entry.if", label %"entry.endif"
entry.if:
  store i32 3601182720, ptr %".2"
  br label %"entry.endif"
entry.endif:
  %".10" = getelementptr i32, ptr %".1", i32 0
  store i32 0, ptr %".10"
  %".12" = getelementptr i32, ptr %".1", i32 1
  store i32 0, ptr %".12"
  %".14" = getelementptr i32, ptr %".1", i32 4
  store i32 0, ptr %".14"
  %".16" = getelementptr i32, ptr %".1", i32 5
  store i32 0, ptr %".16"
  %".18" = getelementptr i32, ptr %".1", i32 6
  %".19" = load i32, ptr %".18"
  %".20" = and i32 %".19", 2147483647
  %".21" = getelementptr i32, ptr %".1", i32 6
  store i32 %".20", ptr %".21"
  ret void
}

define void @"rd6_panel_tick"(ptr %".1", ptr %".2", ptr %".3", ptr %".4", i32 %".5", i32 %".6", i32 %".7") noinline nounwind optsize
{
entry:
  call void @"rd6_panel_cleanup"(ptr %".1", ptr %".2")
  %".10" = icmp eq i32 %".5", 2
  %".11" = icmp ne i32 %".6", 0
  %".12" = icmp eq i32 %".7", 0
  %".13" = and i1 %".11", %".12"
  %".14" = and i1 %".10", %".13"
  %".15" = xor i1 %".14", -1
  br i1 %".15", label %"entry.if", label %"entry.endif"
entry.if:
  call void @"rd6_panel_cancel"(ptr %".2", ptr %".3")
  %".18" = getelementptr i32, ptr %".2", i32 13
  store i32 0, ptr %".18"
  ret void
entry.endif:
  %".21" = mul i32 1, 8
  %".22" = getelementptr i8, ptr %".1", i32 %".21"
  %".23" = load i8, ptr %".22"
  %".24" = zext i8 %".23" to i32
  %".25" = icmp eq i32 %".24", 3
  br i1 %".25", label %"entry.endif.if", label %"entry.endif.endif"
entry.endif.if:
  call void @"rd6_panel_cancel"(ptr %".2", ptr %".3")
  %".28" = getelementptr i32, ptr %".2", i32 13
  store i32 0, ptr %".28"
  ret void
entry.endif.endif:
  %".31" = getelementptr i32, ptr %".2", i32 2
  %".32" = load i32, ptr %".31"
  %".33" = icmp eq i32 %".32", 0
  br i1 %".33", label %"entry.endif.endif.if", label %"entry.endif.endif.endif"
entry.endif.endif.if:
  %".35" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".35"
  br label %"entry.endif.endif.endif"
entry.endif.endif.endif:
  %".38" = getelementptr i32, ptr %".2", i32 3
  %".39" = load i32, ptr %".38"
  %".40" = icmp eq i32 %".39", 0
  br i1 %".40", label %"entry.endif.endif.endif.if", label %"entry.endif.endif.endif.endif"
entry.endif.endif.endif.if:
  %".42" = getelementptr i32, ptr %".2", i32 3
  store i32 2, ptr %".42"
  br label %"entry.endif.endif.endif.endif"
entry.endif.endif.endif.endif:
  %".45" = mul i32 2, 8
  %".46" = getelementptr i8, ptr %".1", i32 %".45"
  %".47" = load i8, ptr %".46"
  %".48" = zext i8 %".47" to i32
  %".49" = icmp uge i32 %".48", 3
  %".50" = mul i32 20, 8
  %".51" = getelementptr i8, ptr %".1", i32 %".50"
  %".52" = load i8, ptr %".51"
  %".53" = zext i8 %".52" to i32
  %".54" = icmp eq i32 %".53", 3
  %".55" = and i1 %".49", %".54"
  br i1 %".55", label %"entry.endif.endif.endif.endif.if", label %"entry.endif.endif.endif.endif.endif"
entry.endif.endif.endif.endif.if:
  %".57" = getelementptr i32, ptr %".2", i32 0
  %".58" = load i32, ptr %".57"
  call void @"rd6_panel_cancel"(ptr %".2", ptr %".3")
  %".60" = getelementptr i32, ptr %".2", i32 13
  store i32 0, ptr %".60"
  %".62" = xor i32 %".58", 1
  %".63" = getelementptr i32, ptr %".2", i32 0
  store i32 %".62", ptr %".63"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 20)
  br label %"loop"
entry.endif.endif.endif.endif.endif:
  %".86" = getelementptr i32, ptr %".2", i32 0
  %".87" = load i32, ptr %".86"
  %".88" = icmp ne i32 %".87", 0
  br i1 %".88", label %"entry.endif.endif.endif.endif.endif.if", label %"entry.endif.endif.endif.endif.endif.endif"
loop:
  %".68" = phi  i32 [0, %"entry.endif.endif.endif.endif.if"], [%".71", %"loop"]
  %".69" = add i32 %".68", 3
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 %".69")
  %".71" = add i32 %".68", 1
  %".72" = icmp ult i32 %".71", 18
  br i1 %".72", label %"loop", label %"done"
done:
  store i32 3601182720, ptr %".3"
  %".75" = xor i32 %".58", 1
  %".76" = getelementptr i32, ptr %".2", i32 5
  store i32 %".75", ptr %".76"
  %".78" = getelementptr i32, ptr %".2", i32 6
  %".79" = load i32, ptr %".78"
  %".80" = xor i32 %".58", 1
  %".81" = shl i32 %".80", 31
  %".82" = or i32 %".79", %".81"
  %".83" = getelementptr i32, ptr %".2", i32 6
  store i32 %".82", ptr %".83"
  ret void
entry.endif.endif.endif.endif.endif.if:
  %".90" = mul i32 3, 8
  %".91" = getelementptr i8, ptr %".1", i32 %".90"
  %".92" = load i8, ptr %".91"
  %".93" = zext i8 %".92" to i32
  %".94" = icmp eq i32 %".93", 3
  br i1 %".94", label %"entry.endif.endif.endif.endif.endif.if.if", label %"entry.endif.endif.endif.endif.endif.if.endif"
entry.endif.endif.endif.endif.endif.endif:
  br i1 %".49", label %"entry.endif.endif.endif.endif.endif.endif.if", label %"entry.endif.endif.endif.endif.endif.endif.endif"
entry.endif.endif.endif.endif.endif.if.if:
  %".96" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".96"
  br label %"entry.endif.endif.endif.endif.endif.if.endif"
entry.endif.endif.endif.endif.endif.if.endif:
  %".99" = mul i32 4, 8
  %".100" = getelementptr i8, ptr %".1", i32 %".99"
  %".101" = load i8, ptr %".100"
  %".102" = zext i8 %".101" to i32
  %".103" = icmp eq i32 %".102", 3
  br i1 %".103", label %"entry.endif.endif.endif.endif.endif.if.endif.if", label %"entry.endif.endif.endif.endif.endif.if.endif.endif"
entry.endif.endif.endif.endif.endif.if.endif.if:
  %".105" = getelementptr i32, ptr %".2", i32 2
  store i32 4, ptr %".105"
  br label %"entry.endif.endif.endif.endif.endif.if.endif.endif"
entry.endif.endif.endif.endif.endif.if.endif.endif:
  %".108" = mul i32 5, 8
  %".109" = getelementptr i8, ptr %".1", i32 %".108"
  %".110" = load i8, ptr %".109"
  %".111" = zext i8 %".110" to i32
  %".112" = icmp eq i32 %".111", 3
  br i1 %".112", label %"entry.endif.endif.endif.endif.endif.if.endif.endif.if", label %"entry.endif.endif.endif.endif.endif.if.endif.endif.endif"
entry.endif.endif.endif.endif.endif.if.endif.endif.if:
  %".114" = getelementptr i32, ptr %".2", i32 2
  store i32 1, ptr %".114"
  br label %"entry.endif.endif.endif.endif.endif.if.endif.endif.endif"
entry.endif.endif.endif.endif.endif.if.endif.endif.endif:
  %".117" = mul i32 6, 8
  %".118" = getelementptr i8, ptr %".1", i32 %".117"
  %".119" = load i8, ptr %".118"
  %".120" = zext i8 %".119" to i32
  %".121" = icmp eq i32 %".120", 3
  br i1 %".121", label %"entry.endif.endif.endif.e...if", label %"entry.endif.endif.endif.e...endif"
entry.endif.endif.endif.e...if:
  %".123" = getelementptr i32, ptr %".2", i32 2
  store i32 2, ptr %".123"
  br label %"entry.endif.endif.endif.e...endif"
entry.endif.endif.endif.e...endif:
  %".126" = mul i32 15, 8
  %".127" = getelementptr i8, ptr %".1", i32 %".126"
  %".128" = load i8, ptr %".127"
  %".129" = zext i8 %".128" to i32
  %".130" = icmp eq i32 %".129", 3
  br i1 %".130", label %"entry.endif.endif.endif.e...endif.if", label %"entry.endif.endif.endif.e...endif.endif"
entry.endif.endif.endif.e...endif.if:
  %".132" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".132"
  br label %"entry.endif.endif.endif.e...endif.endif"
entry.endif.endif.endif.e...endif.endif:
  %".135" = mul i32 16, 8
  %".136" = getelementptr i8, ptr %".1", i32 %".135"
  %".137" = load i8, ptr %".136"
  %".138" = zext i8 %".137" to i32
  %".139" = icmp eq i32 %".138", 3
  br i1 %".139", label %"entry.endif.endif.endif.e...endif.endif.if", label %"entry.endif.endif.endif.e...endif.endif.endif"
entry.endif.endif.endif.e...endif.endif.if:
  %".141" = getelementptr i32, ptr %".2", i32 2
  store i32 6, ptr %".141"
  br label %"entry.endif.endif.endif.e...endif.endif.endif"
entry.endif.endif.endif.e...endif.endif.endif:
  %".144" = mul i32 7, 8
  %".145" = getelementptr i8, ptr %".1", i32 %".144"
  %".146" = load i8, ptr %".145"
  %".147" = zext i8 %".146" to i32
  %".148" = icmp eq i32 %".147", 3
  br i1 %".148", label %"entry.endif.endif.endif.e...endif.endif.endif.if", label %"entry.endif.endif.endif.e...endif.endif.endif.endif"
entry.endif.endif.endif.e...endif.endif.endif.if:
  %".150" = getelementptr i32, ptr %".2", i32 3
  store i32 1, ptr %".150"
  br label %"entry.endif.endif.endif.e...endif.endif.endif.endif"
entry.endif.endif.endif.e...endif.endif.endif.endif:
  %".153" = mul i32 8, 8
  %".154" = getelementptr i8, ptr %".1", i32 %".153"
  %".155" = load i8, ptr %".154"
  %".156" = zext i8 %".155" to i32
  %".157" = icmp eq i32 %".156", 3
  br i1 %".157", label %"entry.endif.endif.endif.e...if.1", label %"entry.endif.endif.endif.e...endif.1"
entry.endif.endif.endif.e...if.1:
  %".159" = getelementptr i32, ptr %".2", i32 3
  store i32 2, ptr %".159"
  br label %"entry.endif.endif.endif.e...endif.1"
entry.endif.endif.endif.e...endif.1:
  %".162" = mul i32 9, 8
  %".163" = getelementptr i8, ptr %".1", i32 %".162"
  %".164" = load i8, ptr %".163"
  %".165" = zext i8 %".164" to i32
  %".166" = icmp eq i32 %".165", 3
  br i1 %".166", label %"entry.endif.endif.endif.e...endif.1.if", label %"entry.endif.endif.endif.e...endif.1.endif"
entry.endif.endif.endif.e...endif.1.if:
  %".168" = getelementptr i32, ptr %".2", i32 3
  store i32 3, ptr %".168"
  br label %"entry.endif.endif.endif.e...endif.1.endif"
entry.endif.endif.endif.e...endif.1.endif:
  %".171" = mul i32 10, 8
  %".172" = getelementptr i8, ptr %".1", i32 %".171"
  %".173" = load i8, ptr %".172"
  %".174" = zext i8 %".173" to i32
  %".175" = icmp eq i32 %".174", 3
  br i1 %".175", label %"entry.endif.endif.endif.e...endif.1.endif.if", label %"entry.endif.endif.endif.e...endif.1.endif.endif"
entry.endif.endif.endif.e...endif.1.endif.if:
  %".177" = getelementptr i32, ptr %".2", i32 3
  store i32 4, ptr %".177"
  br label %"entry.endif.endif.endif.e...endif.1.endif.endif"
entry.endif.endif.endif.e...endif.1.endif.endif:
  %".180" = mul i32 11, 8
  %".181" = getelementptr i8, ptr %".1", i32 %".180"
  %".182" = load i8, ptr %".181"
  %".183" = zext i8 %".182" to i32
  %".184" = icmp eq i32 %".183", 3
  br i1 %".184", label %"entry.endif.endif.endif.e...endif.1.endif.endif.if", label %"entry.endif.endif.endif.e...endif.1.endif.endif.endif"
entry.endif.endif.endif.e...endif.1.endif.endif.if:
  %".186" = getelementptr i32, ptr %".2", i32 13
  store i32 0, ptr %".186"
  %".188" = getelementptr i32, ptr %".2", i32 4
  store i32 9, ptr %".188"
  br label %"entry.endif.endif.endif.e...endif.1.endif.endif.endif"
entry.endif.endif.endif.e...endif.1.endif.endif.endif:
  %".191" = mul i32 12, 8
  %".192" = getelementptr i8, ptr %".1", i32 %".191"
  %".193" = load i8, ptr %".192"
  %".194" = zext i8 %".193" to i32
  %".195" = icmp eq i32 %".194", 3
  br i1 %".195", label %"entry.endif.endif.endif.e...if.2", label %"entry.endif.endif.endif.e...endif.2"
entry.endif.endif.endif.e...if.2:
  %".197" = getelementptr i32, ptr %".2", i32 13
  store i32 1, ptr %".197"
  %".199" = getelementptr i32, ptr %".2", i32 4
  store i32 10, ptr %".199"
  br label %"entry.endif.endif.endif.e...endif.2"
entry.endif.endif.endif.e...endif.2:
  %".202" = mul i32 13, 8
  %".203" = getelementptr i8, ptr %".1", i32 %".202"
  %".204" = load i8, ptr %".203"
  %".205" = zext i8 %".204" to i32
  %".206" = icmp eq i32 %".205", 3
  br i1 %".206", label %"entry.endif.endif.endif.e...endif.2.if", label %"entry.endif.endif.endif.e...endif.2.endif"
entry.endif.endif.endif.e...endif.2.if:
  %".208" = getelementptr i32, ptr %".2", i32 13
  store i32 2, ptr %".208"
  %".210" = getelementptr i32, ptr %".2", i32 4
  store i32 11, ptr %".210"
  br label %"entry.endif.endif.endif.e...endif.2.endif"
entry.endif.endif.endif.e...endif.2.endif:
  %".213" = mul i32 14, 8
  %".214" = getelementptr i8, ptr %".1", i32 %".213"
  %".215" = load i8, ptr %".214"
  %".216" = zext i8 %".215" to i32
  %".217" = icmp eq i32 %".216", 3
  br i1 %".217", label %"entry.endif.endif.endif.e...endif.2.endif.if", label %"entry.endif.endif.endif.e...endif.2.endif.endif"
entry.endif.endif.endif.e...endif.2.endif.if:
  %".219" = getelementptr i32, ptr %".2", i32 13
  store i32 3, ptr %".219"
  %".221" = getelementptr i32, ptr %".2", i32 4
  store i32 12, ptr %".221"
  br label %"entry.endif.endif.endif.e...endif.2.endif.endif"
entry.endif.endif.endif.e...endif.2.endif.endif:
  %".224" = mul i32 19, 8
  %".225" = getelementptr i8, ptr %".1", i32 %".224"
  %".226" = load i8, ptr %".225"
  %".227" = zext i8 %".226" to i32
  %".228" = icmp eq i32 %".227", 3
  %".229" = mul i32 17, 8
  %".230" = getelementptr i8, ptr %".1", i32 %".229"
  %".231" = load i8, ptr %".230"
  %".232" = zext i8 %".231" to i32
  %".233" = icmp eq i32 %".232", 3
  %".234" = or i1 %".228", %".233"
  br i1 %".234", label %"entry.endif.endif.endif.e...endif.2.endif.endif.if", label %"entry.endif.endif.endif.e...endif.2.endif.endif.endif"
entry.endif.endif.endif.e...endif.2.endif.endif.if:
  %".236" = getelementptr i32, ptr %".2", i32 1
  %".237" = load i32, ptr %".236"
  %".238" = xor i32 %".237", 1
  %".239" = getelementptr i32, ptr %".2", i32 1
  store i32 %".238", ptr %".239"
  br label %"entry.endif.endif.endif.e...endif.2.endif.endif.endif"
entry.endif.endif.endif.e...endif.2.endif.endif.endif:
  %".242" = mul i32 18, 8
  %".243" = getelementptr i8, ptr %".1", i32 %".242"
  %".244" = load i8, ptr %".243"
  %".245" = zext i8 %".244" to i32
  %".246" = icmp eq i32 %".245", 3
  br i1 %".246", label %"entry.endif.endif.endif.e...if.3", label %"entry.endif.endif.endif.e...endif.3"
entry.endif.endif.endif.e...if.3:
  %".248" = getelementptr i32, ptr %".2", i32 1
  store i32 0, ptr %".248"
  %".250" = getelementptr i32, ptr %".2", i32 6
  %".251" = load i32, ptr %".250"
  %".252" = or i32 %".251", 2147483648
  %".253" = getelementptr i32, ptr %".2", i32 6
  store i32 %".252", ptr %".253"
  br label %"entry.endif.endif.endif.e...endif.3"
entry.endif.endif.endif.e...endif.3:
  %".256" = mul i32 20, 8
  %".257" = getelementptr i8, ptr %".1", i32 %".256"
  %".258" = load i8, ptr %".257"
  %".259" = zext i8 %".258" to i32
  %".260" = icmp uge i32 %".259", 3
  %".261" = getelementptr i32, ptr %".2", i32 6
  %".262" = load i32, ptr %".261"
  %".263" = mul i32 20, 8
  %".264" = getelementptr i8, ptr %".1", i32 %".263"
  %".265" = load i8, ptr %".264"
  %".266" = zext i8 %".265" to i32
  %".267" = icmp ule i32 %".266", 1
  %".268" = and i32 %".262", 2147483647
  %".269" = select  i1 %".267", i32 %".268", i32 %".262"
  %".270" = getelementptr i32, ptr %".2", i32 6
  store i32 %".269", ptr %".270"
  %".272" = and i32 %".269", 2147483648
  %".273" = icmp eq i32 %".272", 0
  %".274" = and i1 %".260", %".273"
  %".275" = getelementptr i32, ptr %".2", i32 1
  %".276" = load i32, ptr %".275"
  %".277" = zext i1 %".274" to i32
  %".278" = or i32 %".276", %".277"
  %".279" = mul i32 18, 8
  %".280" = getelementptr i8, ptr %".1", i32 %".279"
  %".281" = load i8, ptr %".280"
  %".282" = zext i8 %".281" to i32
  %".283" = icmp eq i32 %".282", 3
  %".284" = select  i1 %".283", i32 0, i32 %".278"
  call void @"rd6_panel_publish"(ptr %".2", ptr %".3", i32 %".284")
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  br label %"loop.1"
loop.1:
  %".288" = phi  i32 [0, %"entry.endif.endif.endif.e...endif.3"], [%".291", %"loop.1"]
  %".289" = add i32 %".288", 3
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 %".289")
  %".291" = add i32 %".288", 1
  %".292" = icmp ult i32 %".291", 18
  br i1 %".292", label %"loop.1", label %"done.1"
done.1:
  ret void
entry.endif.endif.endif.endif.endif.endif.if:
  %".296" = mul i32 3, 8
  %".297" = getelementptr i8, ptr %".1", i32 %".296"
  %".298" = load i8, ptr %".297"
  %".299" = zext i8 %".298" to i32
  %".300" = icmp eq i32 %".299", 3
  br i1 %".300", label %"entry.endif.endif.endif.endif.endif.endif.if.if", label %"entry.endif.endif.endif.endif.endif.endif.if.endif"
entry.endif.endif.endif.endif.endif.endif.endif:
  %".440" = getelementptr i32, ptr %".2", i32 4
  %".441" = load i32, ptr %".440"
  %".442" = icmp ne i32 %".441", 0
  br i1 %".442", label %"entry.endif.endif.endif.endif.endif.endif.endif.if", label %"entry.endif.endif.endif.endif.endif.endif.endif.endif"
entry.endif.endif.endif.endif.endif.endif.if.if:
  %".302" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".302"
  %".304" = getelementptr i32, ptr %".2", i32 4
  store i32 5, ptr %".304"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 3)
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  br label %"entry.endif.endif.endif.endif.endif.endif.if.endif"
entry.endif.endif.endif.endif.endif.endif.if.endif:
  %".309" = mul i32 4, 8
  %".310" = getelementptr i8, ptr %".1", i32 %".309"
  %".311" = load i8, ptr %".310"
  %".312" = zext i8 %".311" to i32
  %".313" = icmp eq i32 %".312", 3
  br i1 %".313", label %"entry.endif.endif.endif.endif.endif.endif.if.endif.if", label %"entry.endif.endif.endif.endif.endif.endif.if.endif.endif"
entry.endif.endif.endif.endif.endif.endif.if.endif.if:
  %".315" = getelementptr i32, ptr %".2", i32 2
  store i32 4, ptr %".315"
  %".317" = getelementptr i32, ptr %".2", i32 4
  store i32 4, ptr %".317"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 4)
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  br label %"entry.endif.endif.endif.endif.endif.endif.if.endif.endif"
entry.endif.endif.endif.endif.endif.endif.if.endif.endif:
  %".322" = mul i32 5, 8
  %".323" = getelementptr i8, ptr %".1", i32 %".322"
  %".324" = load i8, ptr %".323"
  %".325" = zext i8 %".324" to i32
  %".326" = icmp eq i32 %".325", 3
  br i1 %".326", label %"entry.endif.endif.endif.e...if.4", label %"entry.endif.endif.endif.e...endif.4"
entry.endif.endif.endif.e...if.4:
  %".328" = getelementptr i32, ptr %".2", i32 2
  store i32 1, ptr %".328"
  %".330" = getelementptr i32, ptr %".2", i32 4
  store i32 1, ptr %".330"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 5)
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  br label %"entry.endif.endif.endif.e...endif.4"
entry.endif.endif.endif.e...endif.4:
  %".335" = mul i32 6, 8
  %".336" = getelementptr i8, ptr %".1", i32 %".335"
  %".337" = load i8, ptr %".336"
  %".338" = zext i8 %".337" to i32
  %".339" = icmp eq i32 %".338", 3
  br i1 %".339", label %"entry.endif.endif.endif.e...endif.4.if", label %"entry.endif.endif.endif.e...endif.4.endif"
entry.endif.endif.endif.e...endif.4.if:
  %".341" = getelementptr i32, ptr %".2", i32 2
  store i32 2, ptr %".341"
  %".343" = getelementptr i32, ptr %".2", i32 4
  store i32 2, ptr %".343"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 6)
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  br label %"entry.endif.endif.endif.e...endif.4.endif"
entry.endif.endif.endif.e...endif.4.endif:
  %".348" = mul i32 7, 8
  %".349" = getelementptr i8, ptr %".1", i32 %".348"
  %".350" = load i8, ptr %".349"
  %".351" = zext i8 %".350" to i32
  %".352" = icmp eq i32 %".351", 3
  br i1 %".352", label %"entry.endif.endif.endif.e...endif.4.endif.if", label %"entry.endif.endif.endif.e...endif.4.endif.endif"
entry.endif.endif.endif.e...endif.4.endif.if:
  %".354" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".354"
  %".356" = getelementptr i32, ptr %".2", i32 3
  store i32 1, ptr %".356"
  %".358" = getelementptr i32, ptr %".2", i32 4
  store i32 5, ptr %".358"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 7)
  br label %"entry.endif.endif.endif.e...endif.4.endif.endif"
entry.endif.endif.endif.e...endif.4.endif.endif:
  %".362" = mul i32 8, 8
  %".363" = getelementptr i8, ptr %".1", i32 %".362"
  %".364" = load i8, ptr %".363"
  %".365" = zext i8 %".364" to i32
  %".366" = icmp eq i32 %".365", 3
  br i1 %".366", label %"entry.endif.endif.endif.e...endif.4.endif.endif.if", label %"entry.endif.endif.endif.e...endif.4.endif.endif.endif"
entry.endif.endif.endif.e...endif.4.endif.endif.if:
  %".368" = getelementptr i32, ptr %".2", i32 2
  store i32 6, ptr %".368"
  %".370" = getelementptr i32, ptr %".2", i32 3
  store i32 1, ptr %".370"
  %".372" = getelementptr i32, ptr %".2", i32 4
  store i32 6, ptr %".372"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 8)
  br label %"entry.endif.endif.endif.e...endif.4.endif.endif.endif"
entry.endif.endif.endif.e...endif.4.endif.endif.endif:
  %".376" = mul i32 9, 8
  %".377" = getelementptr i8, ptr %".1", i32 %".376"
  %".378" = load i8, ptr %".377"
  %".379" = zext i8 %".378" to i32
  %".380" = icmp eq i32 %".379", 3
  br i1 %".380", label %"entry.endif.endif.endif.e...if.5", label %"entry.endif.endif.endif.e...endif.5"
entry.endif.endif.endif.e...if.5:
  %".382" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".382"
  %".384" = getelementptr i32, ptr %".2", i32 3
  store i32 2, ptr %".384"
  %".386" = getelementptr i32, ptr %".2", i32 4
  store i32 5, ptr %".386"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 9)
  br label %"entry.endif.endif.endif.e...endif.5"
entry.endif.endif.endif.e...endif.5:
  %".390" = mul i32 10, 8
  %".391" = getelementptr i8, ptr %".1", i32 %".390"
  %".392" = load i8, ptr %".391"
  %".393" = zext i8 %".392" to i32
  %".394" = icmp eq i32 %".393", 3
  br i1 %".394", label %"entry.endif.endif.endif.e...endif.5.if", label %"entry.endif.endif.endif.e...endif.5.endif"
entry.endif.endif.endif.e...endif.5.if:
  %".396" = getelementptr i32, ptr %".2", i32 2
  store i32 6, ptr %".396"
  %".398" = getelementptr i32, ptr %".2", i32 3
  store i32 2, ptr %".398"
  %".400" = getelementptr i32, ptr %".2", i32 4
  store i32 6, ptr %".400"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 10)
  br label %"entry.endif.endif.endif.e...endif.5.endif"
entry.endif.endif.endif.e...endif.5.endif:
  %".404" = mul i32 11, 8
  %".405" = getelementptr i8, ptr %".1", i32 %".404"
  %".406" = load i8, ptr %".405"
  %".407" = zext i8 %".406" to i32
  %".408" = icmp eq i32 %".407", 3
  br i1 %".408", label %"entry.endif.endif.endif.e...endif.5.endif.if", label %"entry.endif.endif.endif.e...endif.5.endif.endif"
entry.endif.endif.endif.e...endif.5.endif.if:
  %".410" = getelementptr i32, ptr %".2", i32 2
  store i32 5, ptr %".410"
  %".412" = getelementptr i32, ptr %".2", i32 3
  store i32 3, ptr %".412"
  %".414" = getelementptr i32, ptr %".2", i32 4
  store i32 5, ptr %".414"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 11)
  br label %"entry.endif.endif.endif.e...endif.5.endif.endif"
entry.endif.endif.endif.e...endif.5.endif.endif:
  %".418" = mul i32 12, 8
  %".419" = getelementptr i8, ptr %".1", i32 %".418"
  %".420" = load i8, ptr %".419"
  %".421" = zext i8 %".420" to i32
  %".422" = icmp eq i32 %".421", 3
  br i1 %".422", label %"entry.endif.endif.endif.e...endif.5.endif.endif.if", label %"entry.endif.endif.endif.e...endif.5.endif.endif.endif"
entry.endif.endif.endif.e...endif.5.endif.endif.if:
  %".424" = getelementptr i32, ptr %".2", i32 2
  store i32 6, ptr %".424"
  %".426" = getelementptr i32, ptr %".2", i32 3
  store i32 3, ptr %".426"
  %".428" = getelementptr i32, ptr %".2", i32 4
  store i32 6, ptr %".428"
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 12)
  br label %"entry.endif.endif.endif.e...endif.5.endif.endif.endif"
entry.endif.endif.endif.e...endif.5.endif.endif.endif:
  %".432" = getelementptr i32, ptr %".2", i32 4
  %".433" = load i32, ptr %".432"
  %".434" = icmp ne i32 %".433", 0
  br i1 %".434", label %"entry.endif.endif.endif.e...if.6", label %"entry.endif.endif.endif.e...endif.6"
entry.endif.endif.endif.e...if.6:
  call void @"rd6_panel_consume"(ptr %".1", ptr %".2", ptr %".4", i32 2)
  call void @"rd6_panel_publish"(ptr %".2", ptr %".3", i32 1)
  br label %"entry.endif.endif.endif.e...endif.6"
entry.endif.endif.endif.e...endif.6:
  ret void
entry.endif.endif.endif.endif.endif.endif.endif.if:
  call void @"rd6_panel_cancel"(ptr %".2", ptr %".3")
  br label %"entry.endif.endif.endif.endif.endif.endif.endif.endif"
entry.endif.endif.endif.endif.endif.endif.endif.endif:
  ret void
}

define void @"rd6_panel_wrapper"() noinline nounwind optsize
{
entry:
  %".2" = inttoptr i32 536871484 to ptr
  %".3" = load i32, ptr %".2"
  %".4" = inttoptr i32 536871728 to ptr
  %".5" = load i32, ptr %".4"
  %".6" = inttoptr i32 536875328 to ptr
  %".7" = load i32, ptr %".6"
  %".8" = or i32 %".5", %".7"
  %".9" = or i32 %".3", %".8"
  %".10" = inttoptr i32 536873236 to ptr
  %".11" = inttoptr i32 536879148 to ptr
  %".12" = inttoptr i32 536879104 to ptr
  %".13" = inttoptr i32 536871472 to ptr
  %".14" = inttoptr i32 536871520 to ptr
  %".15" = load i8, ptr %".14"
  %".16" = zext i8 %".15" to i32
  %".17" = inttoptr i32 536873908 to ptr
  %".18" = load i32, ptr %".17"
  call void @"rd6_panel_tick"(ptr %".10", ptr %".11", ptr %".12", ptr %".13", i32 %".16", i32 %".18", i32 %".9")
  %".20" = inttoptr i32 134235513 to void ()*
  call void %".20"()
  ret void
}
