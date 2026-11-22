local P = class("HalloweenResult", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Bottom = self:find("Bottom", self.AnimRoot)
    local Top = self:find("Top", self.AnimRoot)
    local Center = self:find("Center", self.AnimRoot)
    local LeftTop = self:find("LeftTop", self.AnimRoot)

    self.LoseBottom = self:find("Defeat", Bottom)
    self.WinBottom = self:find("Success", Bottom)
    self.LoseTop = self:find("Defeat", Top)
    self.WinTop = self:find("Success", Top)
    self.LoseCenter = self:find("Defeat", Center)
    self.WinCenter = self:find("Success", Center)

    self.isWin = false
    self.ctrlable = false

    bee.addClick(self:find("LobbyButton", LeftTop), function ()
        Game:playSound("ui_button_confirm")
        self:onBtClose()
    end)
end

function P:onShow()
    self.isWin = self._params and self._params.isWin or false
    self.curLevel = self._params and self._params.level or BalBattleModel.curLevel
    self.score = self._params and self._params.score or 0
    self.score = math.floor(self.score)
    self.hisScore = self._params and self._params.hisScore > 0 and true or false
    self.rewards = self._params and self._params.rewards or {}
    self.endlessTime = BalBattleModel.endlessTime

    self.WinBottom:SetActive(self.isWin)
    self.WinTop:SetActive(self.isWin)
    self.WinCenter:SetActive(self.isWin)
    self.LoseBottom:SetActive(not self.isWin)
    self.LoseTop:SetActive(not self.isWin)
    self.LoseCenter:SetActive(not self.isWin)

    if self.isWin then
        Game:playSound("sound_SNG_win")
        self._openAnim, self._closeAnim = "UI_1_HalloweenResult_Success_into", "UI_1_HalloweenResult_Success_back"
        AnimationMgr:playAnim(self.AnimRoot, self._openAnim)
        self:setWinPart()
    else
        Game:playSound("sound_SNG_lose")
        self._openAnim, self._closeAnim = "UI_1_HalloweenResult_Defeat_into", "UI_1_HalloweenResult_Defeat_back"
        AnimationMgr:playAnim(self.AnimRoot, self._openAnim)
        self:setLosePart()
    end
end

--胜利
function P:setWinPart()
    local lan = LanguageManager:getLanguage()
    self.Title = self:find("Title/Main", self.WinCenter)
    local childCount = self.Title.transform.childCount
    for i = 1, childCount do
        local titleItem = self.Title.transform:GetChild(i - 1)
        titleItem.gameObject:SetActive(titleItem.name == lan)
    end

    self.UpgradePart = self:find("Main/Upgrade", self.WinCenter)
    self.UpgradePart:SetActive(false)
    self.EndlessPart = self:find("Main/Endless", self.WinCenter)
    self.EndlessPart:SetActive(false)
    self.ScorePart = self:find("Main/Score", self.WinCenter)
    self.ScorePart:SetActive(false)
    self.ChallengeButton = self:find("ChallengeButton", self.WinCenter)
    self.ChallengeButton:SetActive(false)
    self.ReplayButton = self:find("ReplayButton", self.WinCenter)
    self.ReplayButton:SetActive(false)

    local cfg = tpl_fate_main_level[self.curLevel]
    self:setUpgradePart(cfg.upgrade)
end
function P:setUpgradePart(upgrade)
    if upgrade == nil then
        self:showReward()
        return
    end

    self.UpgradePart:SetActive(true)
    local cardType = self:find("Title/CardType", self.UpgradePart)
    local lv = self:find("Title/Lv", self.UpgradePart)
    local chipVal = self:find("Integral/chipValue", self.UpgradePart)
    local powerVal = self:find("Integral/powerValue", self.UpgradePart)
    local chipFx = self:find("Integral/Chip/Eff_poker_Joker_px_sj", self.UpgradePart)
    chipFx:SetActive(false)
    local powerFx = self:find("Integral/Power/Eff_poker_Joker_px_sj", self.UpgradePart)
    powerFx:SetActive(false)
    local titleRoot = self:find("Title", self.UpgradePart):GetComponent("RectTransform")

    local lvCfg = BalBattleModel:getCardTypeLvId(upgrade[1])
    bee.setText(cardType, _T(POKER_TYPE_NAME[lvCfg.card_type]))
    bee.setText(lv, _T("TAB_JOKER_DEC_17") .. " " .. lvCfg.level)
    bee.setText(chipVal, lvCfg.scores)
    bee.setText(powerVal, lvCfg.multiple)

    CU.Canvas.ForceUpdateCanvases()
    CU.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(titleRoot)
    BalBattleModel:cardTypeLvUp()

    self:once(1.5, function ()
        local nextLvCfg = BalBattleModel:getCardTypeLvId(upgrade[1])
        bee.setText(lv, _T("TAB_JOKER_DEC_17") .. " " .. nextLvCfg.level)
        chipFx:SetActive(true)
        powerFx:SetActive(true)
        bee.setText(chipVal, nextLvCfg.scores)
        bee.setText(powerVal, nextLvCfg.multiple)
        CU.Canvas.ForceUpdateCanvases()
        CU.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(titleRoot)
        self:once(2.3, function ()
            --self.UpgradePart:SetActive(false)
            self:fadeCanvasGroup(self.UpgradePart, true)
            self:showReward()
        end)
    end)
end

function P:showReward()
    self.ctrlable = true
    local cfg = tpl_fate_main_level[self.curLevel]
    
    if cfg.is_infinite and self.endlessTime >= cfg.count then
        self.EndlessPart:SetActive(true)
        self.ScorePart:SetActive(false)
        self:fadeCanvasGroup(self.EndlessPart, false)
        local limitValue = self:find("Limit/Value", self.EndlessPart)
        local scoreTitle = self:find("Record/Title/Text", self.EndlessPart)
        local scoreStr = self:find("Record/Value", self.EndlessPart)
        local newRecord = self:find("Record/halloween_result_success_score_new_zh", self.EndlessPart)

        local curCount = self.endlessTime * cfg.rewards[2]
        local limitCount = cfg.count * cfg.rewards[2]
        bee.setText(limitValue, string.format("%d/%d", curCount, limitCount))
        bee.setText(scoreTitle, self.hisScore and _T("TAB_JOKER_DEC_14") or _T("TAB_JOKER_DEC_30"))
        bee.setText(scoreStr, _N2(self.score))
        newRecord:SetActive(self.hisScore)

        self.ChallengeButton:SetActive(false)
        self.ReplayButton:SetActive(true)
        bee.addClick(self.ReplayButton, function ()
            Game:playSound("ui_button_confirm")
            self:challengeEvent()
            bee.logEvent("joker-ingame-rechallenge", BalBattleModel.curLevel)
        end, true)
    else
        self.EndlessPart:SetActive(false)
        self.ScorePart:SetActive(true)
        self:fadeCanvasGroup(self.ScorePart, false)

        local scoreTitle = self:find("Record/Title/Text", self.ScorePart)
        local scoreStr = self:find("Record/Value", self.ScorePart)
        local newRecord = self:find("Record/halloween_result_success_score_new_zh", self.ScorePart)
        bee.setText(scoreTitle, self.hisScore and _T("TAB_JOKER_DEC_14") or _T("TAB_JOKER_DEC_30"))
        bee.setText(scoreStr, _N2(self.score))
        newRecord:SetActive(self.hisScore)

        local rewardContent = self:find("Reward/Content", self.ScorePart)
        local rewardItem = self:find("Reward/PropItem", self.ScorePart)
        for _,v in pairs(self.rewards) do
            local itemNode = CU.GameObject.Instantiate(rewardItem, rewardContent.transform, false)
            itemNode:SetActive(true)
            PropItem:create(itemNode, v):bindTips()
        end

        local btn = nil
        if cfg.is_infinite then
            btn = self.ReplayButton
            self.ChallengeButton:SetActive(false)
            self.ReplayButton:SetActive(true)
        else
            btn = self.ChallengeButton
            self.ChallengeButton:SetActive(true)
            self.ReplayButton:SetActive(false)
        end
        
        bee.addClick(btn, function ()
            Game:playSound("ui_button_confirm")
            self:challengeEvent()
            bee.logEvent("joker-ingame-next", BalBattleModel.curLevel)
        end, true)
    end
end

--失败
function P:setLosePart()
    self.ctrlable = true
    local lan = LanguageManager:getLanguage()
    self.Title = self:find("Title/Main", self.LoseCenter)
    local childCount = self.Title.transform.childCount
    for i = 1, childCount do
        local titleItem = self.Title.transform:GetChild(i - 1)
        titleItem.gameObject:SetActive(titleItem.name == lan)
    end

    local scoreTitle = self:find("Main/Title/Text", self.LoseCenter)
    local scoreStr = self:find("Main/Value", self.LoseCenter)
    local newRecord = self:find("Main/halloween_result_success_score_new_zh", self.LoseCenter)
    bee.setText(scoreTitle, self.hisScore and _T("TAB_JOKER_DEC_14") or _T("TAB_JOKER_DEC_30"))
    bee.setText(scoreStr, _N2(self.score))
    newRecord:SetActive(self.hisScore)

    bee.addClick(self:find("RetryButton", self.LoseCenter), function ()
        self:challengeEvent()
        bee.logEvent("joker-ingame-rechallenge", BalBattleModel.curLevel)
    end)
end

function P:challengeEvent()
    local action = function ()
        BalBattleModel:startChallenge()
    end
    AnimationMgr:playAnim(self.AnimRoot, self._closeAnim, action)
end
function P:evt_balatroGameStart()
    Game:playSound("sound_balatro_enter")
    bee.enterScene("GameScene", {onEnter = function()
        UiManager:showUI("HalloweenJoker")
    end})
end


function P:fadeCanvasGroup(node, fade, time)
    local canvasGroup = node:GetComponent("CanvasGroup")
    local oriVal = canvasGroup.alpha
    local tarVal = fade and 0 or 1
    bee.tween():toFloat(oriVal, tarVal, time or 0.25, function (v)
        canvasGroup.alpha = v
    end):onComplete(function ()
        if fade then
            node:SetActive(false)
        end
    end)
end

function P:onBtClose()
    if not self.ctrlable then
        return
    end

    local action = function ()
        BalBattleModel:returnMainView()
    end

    self:hideUI(action)
end

return P