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

    self.RightList = self:find("RightList", self.Center)
    self.Item1 = self:find("Item1", self.RightList)
    self.Item1:SetActive(false)

    bee.addClick(self:find("UpgradeButton", self.LevelInfo), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("VIP")
        bee.logEvent("level-levelup")
    end)
    bee.addClick(self:find("PlayButton", self.Center), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("OmahaBlinds")
        bee.logEvent("level-playnow")
    end)
    bee.addClick(self:find("InfoButton", self.Center), function()
        Game:playSound("ui_button_confirm")
        self.TipsMask:SetActive(not self.TipsMask.activeSelf)
        bee.logEvent("level-rules")
    end)
    bee.addClick(self.TipsMask, function()
        self.TipsMask:SetActive(false)
    end)
    bee.addClick(self:find("CloseButton", self.Center), function()
        self:hideUI()
    end)

    self.ListRight = UiListEx:create(self.RightList)
    self.ListRight:setWidth(160)
    self.ListRight:setCreateFunc(function(item)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListRight:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    self._unlockIncos = {}
    for _, v in ipairs(tpl_system_info_list) do
        self._unlockIncos[v.level] = v
    end
end

function P:onShow()
    self.ListRight._list.enabled = false
    self:once(0.15, function()
        self.ListRight:setDatas(tpl_level_list, true, false)
        for k, v in ipairs(tpl_level_list) do
            if v.id == PlayerModel:getCurLevel() then
                self.ListRight:moveToYItem(k, nil, nil, nil, false)
                break
            end
        end
        self.ListRight:refreshUi(true)
        self:once(0.7, function()
            self.ListRight._list.enabled = true
        end)
    end)

    self._curData = tpl_level[PlayerModel:getCurLevel()]
    self:refreshUI()

    self:levelGuide()
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

function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    local level_item_bg_01 = self:find("level_item_bg_01", Ani_root)
    bee.setText(self:find("TextName", Ani_root), _T(data.name))
    bee.setText(self:find("Rank/TextLevel", Ani_root), data.id)
    bee.setIcon(self:find("Rank/icon_rank_01", Ani_root), data.icon)

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
    self:find("Tag", Ani_root):SetActive(data.id >= PlayerModel:getCurLevel())
    if data.id == PlayerModel:getCurLevel() or data.id == PlayerModel:getCurLevel() + 1 then
        self:find("Tag/level_list_tag_02", Ani_root):SetActive(data.id > PlayerModel:getCurLevel())
        self:find("Tag/level_list_tag_01", Ani_root):SetActive(data.id == PlayerModel:getCurLevel())
    else
        self:find("Tag", Ani_root):SetActive(false)
    end
    local info = self._unlockIncos[data.id]
    local FunctionButton = self:find("FunctionButton", level_item_bg_01)
    if info then
        level_item_bg_01:SetActive(true)
        bee.setText(self:find("FunctionButton/TextFunction", level_item_bg_01), _T(info.name_level))
        bee.setIcon(self:find("FunctionButton/level_button_function", level_item_bg_01), info.icon)
        bee.addClick(FunctionButton, function()
            UiManager:showUI("CommonTextTipUD", {text = _T(info.dec2), target = FunctionButton})
        end, true)
    else
        level_item_bg_01:SetActive(false)
    end
    if data.rewards then
        self:find("Icon", Ani_root):SetActive(true)
        PropItem:bindItemNode(self:find("Icon", Ani_root), {item_id = data.rewards[1], num = data.rewards[2]})
        : bindTips()
    else
        self:find("Icon", Ani_root):SetActive(false)
    end
end

function P:refreshTodayHands()
    local hands = PlayerModel:getTodayHands()
    if hands >= VipModel:getExpHands() then
        hands = VipModel:getExpHands()
    end
    local str = string.format("%d<color=#373737>/%d</color>", hands, VipModel:getExpHands())
    bee.setText(self.TextHands, str)

    hands = PlayerModel:getTodaySngHands()
    if hands >= VipModel:getExpTournament() then
        hands = VipModel:getExpTournament()
    end
    local str = string.format("%d<color=#373737>/%d</color>", hands, VipModel:getExpTournament())
    bee.setText(self.TextSngHands, str)
end

function P:evt_GetUserLevelInfoRSP(msg)
    if 0 == msg.code then
        PlayerModel:setTodayHands(msg.hands, msg.sng_hands)
        self:refreshTodayHands()
    end
end

function P:evt_vipLevelUp()
    self:refreshUI()
end

--引导
function P:levelGuide()
    GuideManager:startSystemGuide(8001, 0.65)
end

