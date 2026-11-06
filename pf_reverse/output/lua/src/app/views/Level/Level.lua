
local P = class("Level", UiFullView)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_InformationMainLevel_into", "UI_1_InformationMainLevel_back"

    self.Center = self:find("AnimRoot/Center")
    self.LevelInfo = self:find("LevelInfo", self.Center)

    self.AttrList = self:find("level_bg_frame_01/AttrList", self.LevelInfo)
    self.Content = self:find("Viewport/Content", self.AttrList)

    self.TextHands = self:find("TextHands", self.Content)
    self.TextSngHands = self:find("TextSngHands", self.Content)
    self.TextExpRate = self:find("TextExpRate", self.Content)
    
    self.TextLevel = self:find("TextLevel", self.LevelInfo)
    self.TextExp = self:find("TextExp", self.LevelInfo)
    self.TextLevelName = self:find("TextLevelName", self.LevelInfo)
    self.LevelSlider = self:find("LevelSlider", self.LevelInfo)
    self.icon_rank_01 = self:find("icon_rank_01", self.LevelInfo)

    self.TipsMask = self:find("TipsMask", self.Center)

    self.RightPart = self:find("RightPart", self.Center)
    self.LastButton = self:find("LastButton", self.RightPart)
    self.NextButton = self:find("NextButton", self.RightPart)
    self.LevelGroupInfo = self:find("LevelInfo", self.RightPart)
    self.LevelList = self:find("LevelList", self.RightPart)
    self.Item1 = self:find("Item1", self.LevelList)
    self.Item1:SetActive(false)
    self.FunRoot = self:find("FunRoot", self.LevelList)
    self.FunRoot:SetActive(false)
    self.FunItem = self:find("Fun1", self.FunRoot)

    self.PlayButton = self:find("PlayButton", self.Center)
    self.GreyPlayButton = self:find("GreyPlayButton", self.Center)

    self.InfoButton = self:find("InfoButton", self.Center)
    self.InfoButton:SetActive(not bee.isInGame())

    bee.addClick(self:find("UpgradeButton", self.LevelInfo), function()
        if self._params and self._params.from == "table" then
            UiManager:showToast(_T("LAB_LEVEL_TEXT_18"))
            return
        end
        Game:playSound("ui_button_confirm")
        UiManager:showUI("VIP")
        bee.logEvent("level-levelup")
    end)
    bee.addClick(self.PlayButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("OmahaBlinds")
        bee.logEvent("level-playnow")
    end)
    bee.addClick(self.GreyPlayButton, function()
        UiManager:showToast(_T("LAB_LEVEL_TEXT_18"))
    end)

    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        self:reGuide()
        -- self.TipsMask:SetActive(not self.TipsMask.activeSelf)
        -- bee.logEvent("level-rules")
    end)
    bee.addClick(self.TipsMask, function()
        self.TipsMask:SetActive(false)
    end)
    bee.addClick(self:find("CloseButton", self.Center), function()
        self:hideUI()
    end)

    bee.addClick(self.LastButton, function ()
        Game:playSound("ui_button_confirm")
        local index = self.curLvGroupIndex - 1
        self:refreshRightUI(index)
        bee.logEvent("level-previous")
    end)
    bee.addClick(self.NextButton, function ()
        Game:playSound("ui_button_confirm")
        local index = self.curLvGroupIndex + 1
        self:refreshRightUI(index)
        bee.logEvent("level-next")
    end)

    self.curLvGroupIndex = 0
    self.ListRight = UiListEx:create(self.LevelList)
    self.ListRight:setWidth(160)
    self.ListRight:setCreateFunc(function(item)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListRight:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    self._unlockIncos = {}
    for _, v in ipairs(tpl_system_info_list) do
        if self._unlockIncos[v.level] == nil then
            self._unlockIncos[v.level] = {}
        end
        table.insert(self._unlockIncos[v.level], v)
    end
    self.funUsingList = {}
    self.funIdleList = {}

    self.funTweeners = {}
end

function P:onShow()
    -- self.ListRight._list.enabled = false
    -- self:once(0.15, function()
    --     self.ListRight:setDatas(tpl_level_list, true, false)
    --     for k, v in ipairs(tpl_level_list) do
    --         if v.id == PlayerModel:getCurLevel() then
    --             self.ListRight:moveToYItem(k, nil, nil, nil, false)
    --             break
    --         end
    --     end
    --     self.ListRight:refreshUi(true)
    --     self:once(0.7, function()
    --         self.ListRight._list.enabled = true
    --     end)
    -- end)

    self._curData = tpl_level[PlayerModel:getCurLevel()]
    self:refreshUI()
    self:refreshRightUI()

    self:levelGuide()

    if self._params and self._params.from == "table" then
        self.GreyPlayButton:SetActive(true)
        self.PlayButton:SetActive(false)
    else
        self.GreyPlayButton:SetActive(false)
        self.PlayButton:SetActive(true)
    end
end

function P:refreshUI()
    bee.setText(self.TextLevelName, _T(self._curData.name))
    bee.setText(self.TextLevel, _F("LAB_LEVEL_TEXT_5", self._curData.id))
    self:refreshTodayHands()
    bee.setText(self.TextExpRate, "" .. (VipModel:getVipAdd() / 10) .. "%")
    bee.setIcon(self.icon_rank_01, self._curData.icon)

    if PlayerModel:getCurLevel() < tpl_level_list[#tpl_level_list].id then
        bee.setText(self.TextExp, "" .. PlayerModel:getExp() .. "/" .. tpl_level[PlayerModel:getCurLevel() + 1].xp_up)
        bee.setSliderValue(self.LevelSlider, PlayerModel:getExp() / tpl_level[PlayerModel:getCurLevel() + 1].xp_up)
    else
        bee.setText(self.TextExp, _T("LAB_LEVEL_TEXT_6"))
        bee.setSliderValue(self.LevelSlider, 1)
    end

    Net:sendReq("pb.GetUserLevelInfoREQ", {})
end

function P:refreshRightUI(sltIndex)
    local lvGroupIndex = 0
    local lvGroupCfg = nil

    --获取等级组
    if sltIndex == nil then
        for _,v in pairs(tpl_level_info) do
            if v.level_range[1] <= PlayerModel:getCurLevel() and v.level_range[2] >= PlayerModel:getCurLevel() then
                lvGroupIndex = v.id
                lvGroupCfg = v
                break
            end
        end
    else
        lvGroupIndex = sltIndex
        lvGroupCfg = tpl_level_info[lvGroupIndex]
    end

    if lvGroupCfg == nil then
        lvGroupIndex = #tpl_level_info
        lvGroupCfg = tpl_level_info[lvGroupIndex]
    end

    self.curLvGroupIndex = lvGroupIndex
    self.LastButton:SetActive(lvGroupIndex ~= 1)
    self.NextButton:SetActive(lvGroupIndex ~= #tpl_level_info)

    bee.setIcon(self:find("Icon", self.LevelGroupInfo), lvGroupCfg.icon)
    bee.setText(self:find("Name", self.LevelGroupInfo), _T(lvGroupCfg.name))
    local layoutGroup = self.LevelGroupInfo:GetComponent("HorizontalLayoutGroup")
    bee.once(0.02, function()
        layoutGroup.enabled = false
        layoutGroup.enabled = true
    end)

    local lvs = {}
    local strLv = lvGroupCfg.level_range[1]
    local endLv = lvGroupCfg.level_range[2]
    for i = strLv, endLv do
        table.insert(lvs, tpl_level[i])
    end

    --回收funItem
    for _,v in pairs(self.funUsingList) do
        v.transform:SetParent(self.FunRoot.transform, false)
        table.insert(self.funIdleList, v)
    end
    self.funUsingList = {}

    --赋值等级数据
    self.ListRight._list.enabled = false
    self.ListRight:moveToYItem(1, false)
    self.ListRight:setDatas(lvs, true, false)
    for k, v in ipairs(lvs) do
        if v.id == PlayerModel:getCurLevel() then
            self.ListRight:moveToYItem(k, nil, nil, nil, false)
            break
        end
    end
    self.ListRight:refreshUi(true)
    self:once(0.5, function()
        self.ListRight._list.enabled = true
    end)
end

function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    bee.setText(self:find("Index", Ani_root), data.id)
    local funList = self:find("FunList", Ani_root):GetComponent("ScrollRect")
    local noneTip = self:find("level_item_none", Ani_root)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_Level_item_into", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_2_Level_item_idle", Ani_root)
    end

    self:find("Mask", Ani_root):SetActive(data.id < PlayerModel:getCurLevel() and data.id > 1)
    self:find("SelectFrame", Ani_root):SetActive(data.id == PlayerModel:getCurLevel())

    -- self:find("Tag", Ani_root):SetActive(data.id >= PlayerModel:getCurLevel())
    -- if data.id == PlayerModel:getCurLevel() or data.id == PlayerModel:getCurLevel() + 1 then
    --     self:find("Tag/level_list_tag_02", Ani_root):SetActive(data.id > PlayerModel:getCurLevel())
    --     self:find("Tag/level_list_tag_01", Ani_root):SetActive(data.id == PlayerModel:getCurLevel())
    -- else
    --     self:find("Tag", Ani_root):SetActive(false)
    -- end

    local infos = self._unlockIncos[data.id]
    bee.Tween.killByTarget(funList.content)
    funList.content.anchoredPosition = bee.v2zero
    local childCount = funList.content.childCount
    for i = 1, childCount do
        local childItem = funList.content:GetChild(0)
        childItem:SetParent(self.FunRoot.transform, false)
        table.removebyvalue(self.funUsingList, childItem.gameObject)
    end

    if infos then
        funList.gameObject:SetActive(true)
        noneTip:SetActive(false)

        for _,v in pairs(infos) do
            local funItem
            if #self.funIdleList > 0 then
                funItem = self.funIdleList[1]
                table.remove(self.funIdleList, 1)
            else
                funItem = CU.GameObject.Instantiate(self.FunItem)
            end

            funItem.transform:SetParent(funList.content, false)
            bee.setIcon(self:find("Icon", funItem), v.icon)
            bee.setText(self:find("Text", funItem), _T(v.name_level))
            bee.addClick(funItem, function()
                UiManager:showUI("CommonTextTipUD", {text = _T(v.dec2), target = funItem, 
                    closeCb = function() self:swFunTweener(true, data.id) end})
                self:swFunTweener(false, data.id)
            end, true)

            table.insert(self.funUsingList, funItem.gameObject)
        end

        local infoCount = #infos
        if infoCount <= 3 then
            funList.enabled = false
            funList.content.sizeDelta = bee.v2(480, 100)
        else
            funList.enabled = false
            local lenVtr2 = bee.v2(161 * infoCount + 10, 100)
            funList.content.sizeDelta = lenVtr2

            local len = lenVtr2.x
            local s = funList.transform.sizeDelta.x
            if len <= s then
                funList.content.anchoredPosition = bee.v2zero
            else
                local offset = (len - s)
                funList.content.anchoredPosition = bee.v2(0, 0)
                local tweener = bee.tween(funList.content)
                : to(5, {x = -offset})
                : delay(3)
                : to(0, {x = 0})
                : loop(-1)
                : link()
                : setTarget()

                self.funTweeners[data.id] = {tweener = tweener, running = true}
            end
        end
        

        -- level_item_bg_01:SetActive(true)
        -- bee.setText(self:find("FunctionButton/TextFunction", level_item_bg_01), _T(info.name_level))
        -- bee.setIcon(self:find("FunctionButton/level_button_function", level_item_bg_01), info.icon)
        -- bee.addClick(FunctionButton, function()
        --     UiManager:showUI("CommonTextTipUD", {text = _T(info.dec2), target = FunctionButton})
        -- end, true)
    else
        funList.gameObject:SetActive(false)
        noneTip:SetActive(true)
    end

    if data.rewards then
        self:find("Item", Ani_root):SetActive(true)
        PropItem:bindItemNode(self:find("Item", Ani_root), {item_id = data.rewards[1], num = data.rewards[2]})
        : bindTips()
    else
        self:find("Item", Ani_root):SetActive(false)
    end
end

function P:refreshTodayHands()
    local hands = PlayerModel:getTodayHands()
    if hands >= VipModel:getExpHands() then
        hands = VipModel:getExpHands()
    end
    local str = string.format("%d<color=#61606e>/%d</color>", hands, VipModel:getExpHands())
    bee.setText(self.TextHands, str)

    hands = PlayerModel:getTodaySngHands()
    if hands >= VipModel:getExpTournament() then
        hands = VipModel:getExpTournament()
    end
    local str = string.format("%d<color=#61606e>/%d</color>", hands, VipModel:getExpTournament())
    bee.setText(self.TextSngHands, str)
end

function P:swFunTweener(running, id)
    local tween = self.funTweeners[id]
    if tween then
        tween.running = running
        if not running then
            tween.tweener:pause()
        else
            tween.tweener:resume()
        end
    end
end

function P:evt_GetUserLevelInfoRSP(msg)
    if 0 == msg.code then
        PlayerModel:setTodayHands(msg.hands, msg.sng_hands + msg.mtt_hands)
        self:refreshTodayHands()
    end
end

function P:evt_vipLevelUp()
    self:refreshUI()
end


--引导
function P:levelGuide()
    if bee.isInHome() then
        GuideManager:startSystemGuide(8001, 0.65)
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:reGuide()
    GuideManager:startSystemGuide(8001, 0, true)
end

return P