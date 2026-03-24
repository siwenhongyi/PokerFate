local P = class("ColorGame", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_ColorGame_into", "UI_1_ColorGame_back"

    self.AnimRoot = self:find("AnimRoot")
    self.Left = self:find("Left", self.AnimRoot)

    self.TipMask = self:find("TipMask", self.Left)
    self.InfoMenu = self:find("InfoMenu", self.Left)
    self.InfoTips = self:find("InfoTips", self.Left)
    self.HistoricalRecords = self:find("HistoricalRecords", self.Left)
    self.RecordTips = self:find("RecordTips", self.Left)
    self.TextGold = self:find("TextGold", self.Left)
    self.GuideBet = self:find("GuideBet", self.Left)
    self.GuideHand = self:find("GuideHand", self.Left)
    self.ImageOperateMask = self:find("ImageOperateMask", self.Left)
    self.BgRweard = self:find("BgRweard", self.Left)
    self.BgRweard:SetActive(false)
    self.TextAdd = self:find("TextAdd", self.Left)
    self.TextAdd:SetActive(false)
    self.IconBalance = self:find("IconBalance", self.Left)
    self.lvlId = 0
    self.Sign = false

    self.BetButtons = {
        self:find("Bet1Button", self.Left),
        self:find("Bet2Button", self.Left),
        self:find("Bet3Button", self.Left),
        self:find("Bet4Button", self.Left),
        self:find("Bet5Button", self.Left),
        self:find("Bet6Button", self.Left),
    }

    self.ChipButtons = {
        self:find("color_game_chip_1", self.Left),
        self:find("color_game_chip_2", self.Left),
        self:find("color_game_chip_3", self.Left),
    }

    self.ImageChips = {
        self:find("color_game_chip_01", self.Left),
        self:find("color_game_chip_02", self.Left),
        self:find("color_game_chip_03", self.Left),
    }

    self.ClearButton = self:find("ClearButton", self.Left)
    self.RetractButton = self:find("RetractButton", self.Left)
    self.DoubleButton = self:find("DoubleButton", self.Left)
    self.RebetButton = self:find("RebetButton", self.Left)
    self.SpinButton = self:find("SpinButton", self.Left)

    self.Ballin = self:find("Ballin", self.Left)
    self.BallinAni_root = self:find("Ani_root", self.Ballin)
    
    self.Balls = {}
    self.BgBallOut = self:find("BgBallOut", self.Left)
    self.EftWin = self:find("EftWin", self.BgBallOut)
    self.EftWin:SetActive(false)
    self.Outs = {
        self:find("color_game_machine_mask_01 (1)/Ball1_ani", self.BgBallOut),
        self:find("color_game_machine_mask_01 (1)/Ball2_ani", self.BgBallOut),
        self:find("color_game_machine_mask_01 (1)/Ball3_ani", self.BgBallOut),
    }
    for _, v in ipairs(self.Outs) do
        v:SetActive(false)
    end

    self.DrawAnims = {
        "UI_2_ColorGame_Balin_1",
        "UI_2_ColorGame_Balin_2",
        "UI_2_ColorGame_Balin_3",
    }

    self.IdleAnims = {
        "UI_2_ColorGame_Balin_idle1",
        "UI_2_ColorGame_Balin_idle2",
        "UI_2_ColorGame_Balin_idle0",
    }

    bee.addClick(self:find("Mask", self.AnimRoot), function()
        if self.HistoricalRecords.activeSelf then
            self.HistoricalRecords:SetActive(false)
            return
        end
        -- self:hideUI()
        bee.emit("evt_hideSideGame")
        self:checkPushGift(self.lvlId)
    end)

    bee.addClick(self.TipMask, function()
        if self.RecordTips.activeSelf then
            self._selectedRecord = nil
             self.ListRecord:refreshShowingUi()
        end
        self.RecordTips:SetActive(false)
        self.TipMask:SetActive(false)
        self.InfoMenu:SetActive(false)
        self.InfoTips:SetActive(false)
    end)
    bee.addClick(self:find("CloseButton", self.Left), function()
        -- self:hideUI()
        bee.emit("evt_hideSideGame")
        self:checkPushGift(self.lvlId)
    end)
    bee.addClick(self:find("InfoButton", self.Left), function()
        Game:playSound("ui_button_confirm")
        self.TipMask:SetActive(true)
        self.InfoMenu:SetActive(true)
        -- self.InfoTips:SetActive(true)
        bee.logEvent("colorgame-menu")
    end)
    bee.addClick(self:find("InfoButton", self.InfoMenu), function()
        bee.logEvent("colorgame-rules")
        self.InfoMenu:SetActive(false)
        self.InfoTips:SetActive(true)
    end)
    bee.addClick(self:find("RecordButton", self.InfoMenu), function()
        bee.logEvent("colorgame-history")
        self.TipMask:SetActive(false)
        self.InfoMenu:SetActive(false)
        self:showRecords()
    end)
    bee.addClick(self.ClearButton, function()
        if self:getBetedSum() <= 0 then
            UiManager:showToast(_T("LAB_COLORGAME_019"))
        else
            Game:playSound("ui_button_confirm")
            for k, v in ipairs(self._betInfos) do
                self._gold = self._gold + v
                self._betInfos[k] = 0
                self._tmpInfos[k] = 0
            end
            self._undos = {}
            self:refreshUI()
        end
        bee.logEvent("colorgame-clear")
    end)
    bee.addClick(self.RetractButton, function()
        if #self._undos > 0 then
            Game:playSound("ui_button_confirm")
            local d = table.remove(self._undos, #self._undos)
            for _, v in ipairs(d) do
                self._betInfos[v.id] = self._betInfos[v.id] - v.value
                self._tmpInfos[v.id] = self._tmpInfos[v.id] - v.value
                self._gold = self._gold + v.value
            end
            self:refreshUI()
        else
            UiManager:showToast(_T("LAB_COLORGAME_019"))
        end
    end)
    bee.addClick(self.DoubleButton, function()
        if not bee.checkCd("color_game_double", 0.2) then
            return
        end
        Game:playSound("ui_button_confirm")
        self:onBtDoubleBet()
        bee.logEvent("colorgame-double")
    end)
    bee.addClick(self.RebetButton, function()
        if not bee.checkCd("color_game_rebet", 0.2) then
            return
        end
        Game:playSound("ui_button_confirm")
        self:onBtRebet()
        bee.logEvent("colorgame-rebet")
    end)

    bee.addClick(self.SpinButton, function()
        if not bee.checkCd("color_game_spin", 2) then
            Game:playSound("ui_button_confirm")
            return
        end
        self.Sign = true
        local bets = {}
        for k, v in ipairs(self._betInfos) do
            if v > 0 then
                table.insert(bets, {id = k + 100, value = v})
            end
        end
        if #bets > 0 then
            SettingModel:setIsStopRefreshGold(true)
            Net:sendReq("pb.ColorGameActionREQ", {
                from_game_type = GameModel.data and GameModel.data:getGameType() or 0,
                bets = bets,
                lvl = self._data.id
            })
            self.GuideHand:SetActive(false)
            Game:playSound("ui_button_confirm")
        else
            UiManager:showToast(_T("LAB_COLORGAME_020"))
        end
    end)

    for k, v in ipairs(self.BetButtons) do
        bee.addClick(v, function()
            if not bee.checkCd("color_game_bet_" .. k, 0.2) then
                return
            end
            self:onBtBetAt(k)
        end)
    end

    for k, v in ipairs(self.ChipButtons) do
        bee.addClick(v, function()
            Game:playSound("ui_button_confirm")
            self:onBtChipAt(k)
        end)
    end

    self._nodeCache = NodeCache:create()
    self._rateName = {"Color[color_game_bet_2x]", "Color[color_game_bet_3x]", "Color[color_game_bet_10x]"}
end

function P:onShow()
    self.HistoricalRecords:SetActive(false)
    self.RecordTips:SetActive(false)

    self._betInfos = {0,0,0,0,0,0} -- bet 信息, key = id, value = gold
    self._tmpInfos = {0,0,0,0,0,0}
    self._lastBets = nil    -- 上次 bet 信息, {{id = id, value = gold}, ...}
    self._undos = {}    -- 撤回列表
    self._chipValues = {0, 0, 0}
    self._gold = PlayerModel:getGold()
    self._recordDatas = {}  -- 历史记录列表 {{bet_data = list, bet_result = {}}}
    self:refreshUI()

    self._drawIndex = 1

    Net:sendReq("pb.GetSideGameConfREQ", {game_type = GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME})
end

function P:afterShow()
    self.BallinAni_root:GetComponent("Animator").enabled = true

    if LocalStore:isTagValid("color_game_menu_tip" .. PlayerModel:getUid()) then
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_COLORGAME_030"), target = self:find("InfoButton", self.Left)})
    end
end

function P:onHide()
    SettingModel:setIsStopRefreshGold(nil)
    if self._rewardSeq then
        self._rewardSeq:Kill()
        self._rewardSeq = nil
    end
end

function P:refreshColorGame()
    self._gold = PlayerModel:getGold()
    self.lvlId = 1
    for k, v in ipairs(self._color_datas) do
        if self._gold >= v.balance then
            self.lvlId = k
        else
            break
        end
    end
    self._data = self._color_datas[self.lvlId]
    for k, v in ipairs(self.ChipButtons) do
        self._chipValues[k] = self._data["chips" .. k]
        bee.setText(self:find("TextChip", v), _N(self._chipValues[k]))
        bee.setText(self:find("TextChip", self.ImageChips[k]), _N(self._chipValues[k]))
        self.ImageChips[k]:SetActive(false)
    end
    self:onBtChipAt(1)
    self:refreshUI()
    self.ImageOperateMask:SetActive(false)
    self:refershRewardArea()
    self.GuideHand:SetActive(false)
end

function P:refreshUI()
    self:refreshRetractButton()
    self:refreshDoubleButton()
    self:refreshGold()
    self:refreshBetInfo()
    local sum = self:getBetedSum()
    self.GuideHand:SetActive(sum > 0)
    self.GuideBet:SetActive(sum <= 0)
end

function P:_addBets(bets)
    local bet = 0
    for k, v in ipairs(bets) do
        bet = bet + v.value
    end
    if self._gold >= bet then
        local dt = 1 / #bets
        if dt > 0.1 then
            dt = 0.1
        end
        for k, v in ipairs(bets) do
            self._betInfos[v.id] = self._betInfos[v.id] + v.value
            self._gold = self._gold - v.value
            self:doFlyChip(nil, v.value, v.id, dt * (k - 1))
        end
        table.insert(self._undos, bets)
        self:refreshUI()
    else
        UiManager:showToast(_T("LAB_COLORGAME_017"))
    end
end

function P:onBtDoubleBet()
    local bets = {}
    for _, v in ipairs(self._undos) do
        for _, vv in ipairs(v) do
            table.insert(bets, vv)
        end
    end
    self:_addBets(self:mergeChips(bets))
end

function P:onBtRebet()
    if self._lastBets then
        self:_addBets(self._lastBets)
    end
end

function P:onBtBetAt(index)
    local value = self._chipValues[self._chipIndex]
    if value + self._betInfos[index] > self._data.maxbet then
        UiManager:showToast(_F("LAB_COLORGAME_018", _N(self._data.maxbet)))
    elseif self._gold >= value then
        self._betInfos[index] = self._betInfos[index] + value
        self._gold = self._gold - value
        table.insert(self._undos, {{id = index, value = value}})
        self:refreshRetractButton()
        self:refreshDoubleButton()
        self:refreshGold()
        self:doFlyChip(self._chipIndex, self._chipValues[self._chipIndex], index)
        -- self:refreshBetInfo(index)
        self.GuideBet:SetActive(false)
        self.GuideHand:SetActive(true)
        Game:playSound("ui_button_confirm")
    else
        UiManager:showToast(_T("LAB_COLORGAME_017"))
    end
end

function P:onBtChipAt(index)
    self._chipIndex = index
    for k, v in ipairs(self.ChipButtons) do
        self:find("color_game_chip_selected", v):SetActive(k == index)
    end
end

local toScale = bee.v3(0.3, 0.3, 0.3)
function P:doFlyChip(chipIndex, chipValue, toIndex, delay)
    if not chipIndex then
        chipIndex = 1
        if chipValue == self._data.chips2 then
            chipIndex = 2
        elseif chipValue == self._data.chips3 then
            chipIndex = 3
        end
    end
    if delay and delay > 0 then
        self:once(delay, function()
            self:_doFlyChip(chipIndex, chipValue, toIndex)
        end)
    else
        self:_doFlyChip(chipIndex, chipValue, toIndex)
    end
end

function P:_doFlyChip(chipIndex, chipValue, toIndex)
    if self._ishide then
        return
    end
    local chip = self._nodeCache:getItem(chipIndex, self.ImageChips[chipIndex], self.Left.transform)
    chip.transform.localPosition = self.ImageChips[chipIndex].transform.localPosition
    chip.transform.localScale = bee.v3one
    bee.tween(chip, true)
    : to(0.4, {position = self.BetButtons[toIndex].transform.position, scale = toScale})
    : onComplete(function()
        self._nodeCache:putItem(chip)
        self._tmpInfos[toIndex] = self._tmpInfos[toIndex] + chipValue
        self:refreshBetInfo(toIndex)
    end)
    : link()
end

function P:refreshGold()
    bee.setText(self.TextGold, _N(self._gold))
end

function P:refreshBetInfo(index)
    if index then
        if self._tmpInfos[index] > 0 then
            local ingame_pot_chip = self:find("ImageChip", self.BetButtons[index])
            self:find("TextBet", self.BetButtons[index]):SetActive(true)
            ingame_pot_chip:SetActive(true)
            local num = self._tmpInfos[index]
            if num < 0 then
                num = 0
            elseif num > self._betInfos[index] then
                num = self._betInfos[index]
            end
            if num > 0 then
                bee.setText(self:find("TextBet", self.BetButtons[index]), _N(num))
                bee.setIcon(ingame_pot_chip, self:getChipIcon(num))
            else
                self:find("TextBet", self.BetButtons[index]):SetActive(false)
                self:find("ImageChip", self.BetButtons[index]):SetActive(false)
            end
        else
            self:find("TextBet", self.BetButtons[index]):SetActive(false)
            self:find("ImageChip", self.BetButtons[index]):SetActive(false)
        end
    else
        for k, _ in ipairs(self._tmpInfos) do
            self:refreshBetInfo(k)
        end
    end
end

function P:refreshRetractButton()
    bee.setGrey(self.ClearButton, self:getBetedSum() <= 0, true)
    bee.setGrey(self.RetractButton, #self._undos == 0, true)
end

function P:refreshDoubleButton()
    self.RebetButton:SetActive(#self._undos == 0 and self._lastBets ~= nil)
    local flag = #self._undos > 0
    if flag then
        local sum = self:getBetedSum()
        if sum <= 0 then
            flag = false
        elseif self._gold < sum then
            flag = false
        else
            for k, v in ipairs(self._betInfos) do
                if v + v > self._data.maxbet then
                    flag = false
                    break
                end
            end
        end
    end
    self.DoubleButton:SetActive(flag)
end

function P:refershRewardArea(ids)
    if not ids then
        for _, v in ipairs(self.BetButtons) do
            self:find("ImageTip", v):SetActive(false)
            self:find("Image2X", v):SetActive(false)
            bee.setGray(self:find("ImageBg", v), false)
        end
    else
        for k, v in ipairs(self.BetButtons) do
            local ImageTip = self:find("ImageTip", v)
            if table.indexof(ids, k + 100) > 0 then
                ImageTip:SetActive(true)
                bee.tween(ImageTip)
                : to(0.5, {opacity = 0.2})
                : to(0.5, {opacity = 1})
                : to(0.5, {opacity = 0.2})
                : to(0.5, {opacity = 1})
                : to(0.5, {opacity = 0.2})
                : to(0.5, {opacity = 1})
                : onComplete(function()
                    ImageTip:SetActive(false)
                end)
                : link()
                bee.setGray(self:find("ImageBg", v), false)
            else
                ImageTip:SetActive(false)
                bee.setGray(self:find("ImageBg", v), true)
            end
        end
        local counts = {0, 0, 0, 0, 0, 0}
        for k, v in ipairs(ids) do
            counts[v - 100] = counts[v - 100] + 1
        end
        local scale = bee.v3(1.2, 1.2, 1.2)
        for k, v in ipairs(counts) do
            if v > 0 then
                local Image2X = self:find("Image2X", self.BetButtons[k])
                Image2X:SetActive(true)
                bee.setIcon(Image2X, self._rateName[v] or self._rateName[1], true)
                Image2X.transform.localScale = bee.v3one
                bee.tween(Image2X)
                : to(0.5, {scale = scale})
                : to(0.5, {scale = bee.v3one})
                : to(0.5, {scale = scale})
                : to(0.5, {scale = bee.v3one})
                : to(0.5, {scale = scale})
                : to(0.5, {scale = bee.v3one})
                : onComplete(function()
                    Image2X:SetActive(false)
                end)
                : link()
            else
            end
        end
    end
end

function P:getChipIcon(num)
    if num >= self._data.chips3 then
        return "Color[color_game_chip_03_s]"
    elseif num >= self._data.chips2 then
        return "Color[color_game_chip_02_s]"
    else
        return "Color[color_game_chip_01_s]"
    end
end

function P:getBetedSum()
    local ret = 0
    for _, v in ipairs(self._betInfos) do
        ret = ret + v
    end
    return ret
end

-- 合并 bet 的数值
function P:mergeChips(bets)
    if #bets >= 10 then
        local tmp = {0, 0, 0, 0, 0, 0}
        for _, v in ipairs(bets) do
            tmp[v.id] = tmp[v.id] + v.value
        end
        local rets = {}
        for k, v in ipairs(tmp) do
            if v > 0 then
                v = self:_mergeChip(rets, k, v, self._data.chips3)
                v = self:_mergeChip(rets, k, v, self._data.chips2)
                v = self:_mergeChip(rets, k, v, self._data.chips1)
            end
        end
        table.shuffle(rets)
        return rets
    end
    return bets
end

function P:_mergeChip(rets, id, value, chips)
    if value >= chips then
        local num = math.floor(value / chips)
        if num > 0 then
            for i = 1, num do
                table.insert(rets, {id = id, value = chips})
            end
            value = value % chips
        end
    end
    return value
end

function P:getBetChips(id)
    local chip = self._betInfos[id]
    local rets = {}
    chip = self:_mergeChip(rets, id, chip, self._data.chips3)
    chip = self:_mergeChip(rets, id, chip, self._data.chips2)
    chip = self:_mergeChip(rets, id, chip, self._data.chips1)
    return rets
end

function P:doShowRewards(msg)
    self:refershRewardArea(msg.ids)
    local sum = 0
    local shockIndex = nil
    for k, v in ipairs(msg.profits) do
        sum = sum + v.profit
        if v.profit > 0 then
            local num = 0
            for _, vv in ipairs(msg.ids) do
                if vv == v.id then
                    num = num + 1
                end
            end
            if not shockIndex or shockIndex < num then
                shockIndex = num
            end
        end
    end
    if sum > 0 then
        bee.vibrate(tpl_vibrate["shock_colorgame" .. shockIndex])
    end
    local seqs = {3}
    if sum > 0 then
        local profitRates = {[0] = 0, 2, 3, 10}
        local counts = {0, 0, 0, 0, 0, 0}
        for k, v in ipairs(msg.ids) do
            counts[v - 100] = counts[v - 100] + 1
        end
        local flyDt = 1.4
        for k, v in ipairs(msg.profits) do
            if v.profit > 0 then
                local chips = self:getBetChips(k)
                local dt = (#chips - 1) * 0.1
                if dt > 0.6 then
                    dt = 0.6
                end
                if dt + 0.8 + 0.6 > flyDt then
                    flyDt = dt + 0.8 + 0.6
                end
            end
        end
        seqs[#seqs + 1] = function()
            self._tmpInfos = {0,0,0,0,0,0}
            self:refreshBetInfo()
            local hitSound = true
            local soundNum = 0
            if self._ishide then
                return
            end
            for k, v in ipairs(msg.profits) do
                if v.profit > 0 then
                    soundNum = soundNum + 1
                    local chipNode = self._nodeCache:getItemWithName("Prefab/Eff_poker_Ui_chouma", self.Left.transform)
                    self._nodeCache:addUsing(chipNode)
                    chipNode.transform.position = self.BgRweard.transform.position
                    local from = chipNode.transform.position
                    local to = self.BetButtons[k].transform.position
                    local center = bee.v3(to.x, (from.y + to.y) / 2)
                    
                    local cmp = CS.BezierAction.BezierTo(chipNode, from, center, to, 0.6)
                    cmp.isLocal = false
                    cmp:OnComplete(function()
                        if hitSound then
                            hitSound = false
                            Game:playSound("sound_Colorgame_hit")
                        end
                        local eft = self._nodeCache:getItemWithName("Prefab/ColorGame/Eff_poker_Ui_colorgame_sd", self.Left.transform)
                        self._nodeCache:addUsing(eft)
                        eft.transform.position = self.BetButtons[k].transform.position
                        CU.GameObject.Destroy(eft, 2)
                        self._nodeCache:putItem(chipNode)
                        
                        local chips = self:getBetChips(k)
                        local flyNums = {0, 0, 0, 0, 0, 0}
                        for _, v in ipairs(chips) do
                            for i = 1, profitRates[counts[k]] do
                                flyNums[k] = flyNums[k] + 1
                                local dt = (flyNums[k] - 1) * 0.1
                                if dt > 0.6 then
                                    dt = math.random(6) / 10
                                end
                                self:once(dt, function()
                                    local chipNode = self._nodeCache:getItemWithName("Prefab/Eff_poker_Ui_chouma", self.Left.transform)
                                    self._nodeCache:addUsing(chipNode)
                                    chipNode.transform.position = self.BetButtons[k].transform.position
                                    local pos = chipNode.transform.localPosition
                                    pos.x, pos.y = pos.x + math.random(60) - 30, pos.y + math.random(60) - 30
                                    chipNode.transform.localPosition = pos
                                    bee.tween(chipNode, true)
                                    : by(0.2, {y = 0.01})
                                    : to(0.6, {position = self.IconBalance.transform.position})
                                    : onComplete(function()
                                        self._nodeCache:putItem(chipNode)
                                    end)
                                    : link()
                                end)
                            end
                        end
                    end)

                    -- bee.tween(chipNode, true)
                    -- : to(0.5, {position = self.BetButtons[k].transform.position})
                    -- : onComplete(function()
                    -- end)
                    -- : link()
                end
            end
            if soundNum > 0 then
                local sounds = {"sound_Colorgame_lwo", "sound_Colorgame_middle", "sound_Colorgame_high"}
                local s = sounds[soundNum]
                if s then
                    Game:playSound(s)
                end
            end
        end
        seqs[#seqs + 1] = flyDt
        seqs[#seqs + 1] = function()
            local TextAdd = CU.GameObject.Instantiate(self.TextAdd, self.Left.transform, false)
            TextAdd.transform.position = self.TextGold.transform.position
            TextAdd:SetActive(true)
            bee.setText(TextAdd, "+" .. _N(sum))
            self._gold = self._gold + sum
            self:refreshGold()
            bee.tween(TextAdd)
            : to(0.5, {position = self.TextAdd.transform.localPosition})
            : link()
            CU.GameObject.Destroy(TextAdd, 0.8)
            bee.vibrate(tpl_vibrate.shock_colorgame4)
        end
        seqs[#seqs + 1] = 2
    end
    seqs[#seqs + 1] = function()
        self.TextAdd:SetActive(false)
        self.ImageOperateMask:SetActive(false)
        self:refershRewardArea()
        self._lastBets = {}
        for _, v in ipairs(self._undos) do
            for _, vv in ipairs(v) do
                table.insert(self._lastBets, vv)
            end
        end
        self._lastBets = self:mergeChips(self._lastBets)
        self._betInfos = {0, 0, 0, 0, 0, 0}
        self._tmpInfos = {0,0,0,0,0,0}
        self._undos = {}
        
        -- self:refreshUI()
        local playedLvlId = self.lvlId
        
        self._gold = PlayerModel:getGold()
        local lvlId = 1
        for k, v in ipairs(self._color_datas) do
            if self._gold >= v.balance then
                lvlId = k
            else
                break
            end
        end
        if lvlId ~= self.lvlId then
            self:refreshColorGame()
        else
            self:refreshUI()
        end
        SettingModel:setIsStopRefreshGold(nil)
        self._rewardSeq = nil

        self:checkPushGift(playedLvlId, sum)

        if not GameModel.data then
            if msg.ids[1] == msg.ids[2] and msg.ids[2] == msg.ids[3] then
                for _, v in ipairs(msg.profits) do
                    if v.id == msg.ids[1] and v.profit > 0 then
                        SdkHelper:startAppReview()
                        break
                    end
                end
            end
        end

        if self.HistoricalRecords.activeSelf then
            self.ListRecord:setDatas(self._recordDatas)
        end
    end
    self._rewardSeq = bee.Tween.sequence(seqs)
end

function P:doShowDrawAnim(msg)
    self._startBoundDt = scheduler.timeSpend
    self._drawIds = {}
    for _, v in ipairs(msg.ids) do
        table.insert(self._drawIds, v)
    end
    for _, v in ipairs(self.Outs) do
        v:SetActive(false)
    end

    if self._drawIndex > #self.DrawAnims then
        self._drawIndex = 1
    end
    AnimationMgr:playAnim(self.BallinAni_root, self.DrawAnims[self._drawIndex], function()
        self._drawIndex = self._drawIndex + 1
        if self._drawIndex > #self.DrawAnims then
            self._drawIndex = 1
        end
        if not bee.isNull(self.BallinAni_root) then
            AnimationMgr:playAnim(self.BallinAni_root, self.DrawAnims[self._drawIndex])
        end
    end)
    local dt = 0.6
    local playDrawSound = true
    bee.tween(self.SpinButton)
    : to(dt * 3, {rotate = bee.v3(0, 0, -360 * 3)}, {rotate = DT.RotateMode.FastBeyond360})
    : ease(DT.Ease.Linear)
    : link()
    self:repeatN(3, dt, function()
        self:onBallDrawed()
        if playDrawSound then
            playDrawSound = false
            Game:playSound("sound_Colorgame_drop")
        end
    end)
    self._inShake = true
    self._shakeDt = 3
    if not self._AnimRootPos then
        self._AnimRootPos = self.AnimRoot.transform.localPosition
    end
end

function P:onBallDrawed()
    local idx = 1
    if idx > 0 and #self._drawIds >= idx then
        local id = table.remove(self._drawIds, idx)
        local ball = self.Outs[3 - #self._drawIds]
        ball:SetActive(true)
        bee.setIcon(self:find("Ball", ball), "Color[color_game_ball_0" .. (id - 100) .. "]")
        -- AnimationMgr:playAnim(ball, "UI_2_ColorGame_Ball1_into")
        if #self._drawIds == 0 then
            self:once(0.3, function()
                self._inShake = nil
                self.AnimRoot.transform.localPosition = self._AnimRootPos
                self.EftWin:SetActive(false)
                self.EftWin:SetActive(true)
            end)
            self:doShowRewards(self._drawMsg)
        end
        return
    end
end

function P:onUpdate(dt)
    if self._inShake then
        self._shakeDt = self._shakeDt + dt
        if self._shakeDt >= 0.05 then
            self._shakeDt = 0
            local pos = CU.Random.insideUnitCircle * 8
            self.AnimRoot.transform.localPosition = bee.v3(pos.x + self._AnimRootPos.x, pos.y + self._AnimRootPos.y)
        end
    end
end

function P:evt_ColorGameActionRSP(msg)
    local record = {bet_data = {}, bet_result = clone(msg.ids)}
    self._drawMsg = msg
    self.ImageOperateMask:SetActive(true)
    self:doShowDrawAnim(msg)

    for i = 1, 6 do
        record.bet_data[i] = {id = i + 100, chips = 0, profit = 0}
    end
    for k, v in ipairs(msg.bets) do
        record.bet_data[k] = {id = v.id, chips = v.value, profit = 0}
        for _, vv in ipairs(msg.profits) do
            if vv.id == v.id then
                record.bet_data[k].profit = vv.profit - v.value
                break
            end
        end
    end
    table.insert(self._recordDatas, 1, record)
    if #self._recordDatas > tpl_constdata.Colorgame_History_Limit then
        table.remove(self._recordDatas)
    end
    for k, v in ipairs(self._recordDatas) do
        v.index = k
    end
    Game:playSound("sound_Colorgame_roll")
end

function P:evt_GetSideGameConfRSP(msg)
    if 0 == msg.code and msg.game_type == GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME then
        self._color_datas = json.decode(msg.conf).tpl_conf
        bee.setText(self:find("Scroll View/Viewport/Content/TextChipTip", self.InfoTips), _F("LAB_COLORGAME_011", _N(self._color_datas[1].maxbet)))
        self:refreshColorGame()
    end
end

function P:evt_refreshTopInfo()
    if self._gold ~= PlayerModel:getGold() then
        self._gold = PlayerModel:getGold()
        for _, v in ipairs(self._betInfos) do
            self._gold = self._gold - v
        end
        self:refreshGold()
    end
end

function P:evt_sideGameViewHide()
    self._nodeCache:clearAll()
    if self._rewardSeq then
        self._rewardSeq:Kill()
        self._rewardSeq = nil
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self._ishide = not isVisible
    if self._ishide then
        self._nodeCache:clearAll()
    end
end

function P:checkPushGift(lvlId, profits)
    local sum = profits or self:getGameProfit()
    SideGameModel:checkPushGift(self.Sign, sum, GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME, lvlId)
    self.Sign = false
end

function P:getGameProfit()
    local sum = 0
    if self._drawMsg == nil then
        return sum
    end
    for _,v in pairs(self._drawMsg.profits) do
        sum = sum + v.profit
    end
    return sum
end

-------------- 历史记录 start --------------
function P:showRecords()
    self.HistoricalRecords:SetActive(true)

    if not self._initRecords then
        self._initRecords = true
        local AnimRoot = self:find("AnimRoot", self.HistoricalRecords)
        local RecordList = self:find("List/RecordList", AnimRoot)
        local Item1 = self:find("Item1", RecordList)
        Item1:SetActive(false)

        bee.addClick(self:find("CloseButton", AnimRoot), function()
            self.HistoricalRecords:SetActive(false)
        end)

        bee.setText(self:find("TextTipLimit", AnimRoot), _F("LAB_COLORGAME_028", tpl_constdata.Colorgame_History_Limit))

        self.ListRecord = UiListEx:create(RecordList)
        self.ListRecord:setWidth(70)
        self.ListRecord:setCreateFunc(function(data)
            return CU.GameObject.Instantiate(Item1)
        end)
        self.ListRecord:setRefreshFunc(function(data, item)
            self:find("color_game_record_list_frame_01", item):SetActive(data.index % 2 == 1)
            self:find("color_game_record_list_frame_02", item):SetActive(data.index % 2 == 0)
            self:find("color_game_record_list_frame_on", item):SetActive(data == self._selectedRecord)

            for k, v in ipairs(data.bet_result) do
                bee.setIcon(self:find("color_game_ball_0" .. k, item), "Color[color_game_ball_0" .. (v - 100) .. "]")
            end
            local profit, chips = 0, 0
            for _, v in ipairs(data.bet_data) do
                chips = chips + v.chips
                profit = profit + v.profit
            end
            if profit > 0 then
                bee.setText(self:find("TextWin", item), _N(profit))
                bee.setText(self:find("TextLose", item), "")
            else
                bee.setText(self:find("TextWin", item), "")
                bee.setText(self:find("TextLose", item), _N(profit))
            end
            bee.setText(self:find("TextBet", item), _N(chips))

            bee.addClick(item, function()
                self:showRecordTips(data, item)
                self.ListRecord:refreshShowingUi()
            end, true)
        end)
    end

    self.RecordTips:SetActive(false)

    Net:sendReq("pb.GetSideGameHisRecordREQ", {game_type = GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME})
end

function P:showRecordTips(data, item)
    self.TipMask:SetActive(true)
    self.RecordTips:SetActive(true)

    self._selectedRecord = data
    for i = 1, 6 do
        local node = self:find("Box/" .. i, self.RecordTips)
        local info = {chips = 0, profit = 0, rate = 0}
        for _, v in ipairs(data.bet_data) do
            if v.id == i + 100 then
                info.chips = v.chips
                info.profit = v.profit
                for _, vv in ipairs(data.bet_result) do
                    if vv == i + 100 then
                        info.rate = info.rate + 1
                    end
                end
                break
            end
        end
        if info.rate > 0 then
            bee.setIcon(self:find("Image2X", node), self._rateName[info.rate] or self._rateName[1], true)
            self:find("Image2X", node):SetActive(true)
            self:find("TextNoReward", node):SetActive(false)
        else
            self:find("Image2X", node):SetActive(false)
            self:find("TextNoReward", node):SetActive(true)
        end
        if info.chips > 0 then
            bee.setText(self:find("TextBet", node), _N(info.chips))
        else
            bee.setText(self:find("TextBet", node), "-")
        end
    end

    local pos = self.RecordTips.transform.position
    pos.y = item.transform.position.y
    self.RecordTips.transform.position = pos
    pos = self.RecordTips.transform.localPosition
    pos.y = pos.y - 211
    local flag = false
    if pos.y < -281 then
        pos.y = -281
        flag = true
    end
    self.RecordTips.transform.localPosition = pos

    local common_result_tips_01_arrow_up = self:find("common_result_tips_01_arrow_up", self.RecordTips)
    if flag then
        if not self._tipArrowUpPos then
            self._tipArrowUpPos = common_result_tips_01_arrow_up.transform.localPosition
        end
        local arrowPos = common_result_tips_01_arrow_up.transform.position
        arrowPos.y = item.transform.position.y
        common_result_tips_01_arrow_up.transform.position = arrowPos
    elseif self._tipArrowUpPos then
        common_result_tips_01_arrow_up.transform.localPosition = self._tipArrowUpPos
    end
end

function P:evt_GetSideGameHisRecordRSP(msg)
    if msg.game_type == GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME then
        self._recordDatas = {}
        if msg.bet_data and "" ~= msg.bet_data then
            local bet_data = json.decode(msg.bet_data)
            local bet_result = json.decode(msg.result)
            for k, v in ipairs(bet_data) do
                table.insert(self._recordDatas, {
                    index = k,
                    bet_data = v,
                    bet_result = bet_result[k] or {},
                })
            end
        end
        self.ListRecord:setDatas(self._recordDatas)
    end
end

