local P = class("CharacterMainBonds", require("app.views.Character.CharacterBase"))

function P:onAwake()
    P.super.onAwake(self)
	self._openAnim, self._closeAnim = "UI_1_CharacterMainBonds_into", ""

    self.ImageMask = self:find("AnimRoot/ImageMask")
    self.ImageMask:SetActive(false)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.BondLevel = self:find("BondLevel", self.Left)
    self.BackButton = self:find("BackButton", self.LeftTop)

    self.character_bond_level_bg = self:find("character_bond_level_bg", self.BondLevel)
    self.TextCurLevel = self:find("TextCurLevel", self.BondLevel)
    self.TextCurLevel2 = self:find("TextCurLevel2", self.BondLevel)
    self.TextBondValue = self:find("TextBondValue", self.character_bond_level_bg)
    self.TextBondTip = self:find("TextBondTip", self.character_bond_level_bg)
    self.TextBondFull = self:find("TextBondFull", self.character_bond_level_bg)

    self.character_bond_bg = self:find("character_bond_bg", self.Right)
    self.TextDailyLeft = self:find("TextDailyLeft", self.character_bond_bg)
    self.InfoButton = self:find("InfoButton", self.character_bond_bg)
    self.GiftButton = self:find("GiftButton", self.character_bond_bg)
    local GiftsList = self:find("GiftsList", self.character_bond_bg)
    self.LevelUpTips = self:find("LevelUpTips", self.Center)
    if self.LevelUpTips then
        self.LevelUpTips:SetActive(false)
    end
    local Item1 = self:find("Item1", GiftsList)
    Item1:SetActive(false)

    self.Pledged = self:find("Pledged", self.Right)
    self.AvailableButton = self:find("AvailableButton", self.Right)

    self.HeartView = self:find("HeartView", self.Bottom)
    self.HeartSlider = self:find("HeartSlider", self.HeartView)
    self.character_bond_heart_line_fg = self:find("character_bond_heart_line_fg", self.HeartSlider)
    self.character_bond_heart_line_oath_fg = self:find("character_bond_heart_line_oath_fg", self.HeartSlider)
    self.character_bond_heart_line_oath_bg = self:find("character_bond_heart_line_oath_bg", self.HeartSlider)

    self.HeartLv1s = {
        self:find("HeartLv1", self.HeartSlider),
        self:find("HeartLv2", self.HeartSlider),
        self:find("HeartLv3", self.HeartSlider),
        self:find("HeartLv4", self.HeartSlider),
        self:find("HeartLv5", self.HeartSlider),
        self:find("HeartLv6", self.HeartSlider),
    }

    local s = self.HeartSlider.transform.sizeDelta
    self._bondProgressSize = self.character_bond_heart_line_fg.transform.sizeDelta
    self._bondProgress = {[0] = 0, 0, 0.20, 0.4, 0.6, 0.8, 1}
    if SCREEN_WIDTH > DESIGN_WIDTH then
        local offset = SCREEN_WIDTH - DESIGN_WIDTH
        s.x = s.x + offset
        self.HeartSlider.transform.sizeDelta = s
        self:find("character_bond_heart_line_bg", self.HeartSlider).transform.sizeDelta = bee.v2(0.8 * s.x, s.y)
        local pos = self.HeartLv1s[1].transform.localPosition
        for i = 1, 6 do 
            self.HeartLv1s[i].transform.localPosition = bee.v3(self._bondProgress[i] * s.x - s.x / 2, pos.y)
        end
        pos = self.character_bond_heart_line_oath_fg.transform.localPosition
        pos.x = (self.HeartLv1s[5].transform.localPosition.x + self.HeartLv1s[6].transform.localPosition.x) / 2
        self.character_bond_heart_line_oath_fg.transform.localPosition = pos
        self.character_bond_heart_line_oath_bg.transform.localPosition = pos
    end
    self._bondProgressSize.x = s.x - 4

    self.GiftsList = UiListEx:create(GiftsList)
    self.GiftsList:setWidth(170)
    self.GiftsList:setRowCount(4)
    self.GiftsList:setRowPostions({-246, -80, 80, 246})
    self.GiftsList:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(Item1)
    end)
    self.GiftsList:setRefreshFunc(function(data, item)
        self:refreshGift(data, item)
    end)

    self.PackageButton = self:find("PackageButton", self.character_bond_bg)
    bee.addClick(self.PackageButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("ShopPledgeExpress", {id = self._role.role_id})
        bee.logEvent("character-bond-oathexpress")
    end)

    for i = 2, 5 do
        local character_icon_box = self:find("character_icon_box", self.HeartLv1s[i])
        bee.addClick(character_icon_box, function()
            Game:playSound("ui_button_confirm")
            local rewards = CharacterModel:getRoleBondsRewards(self._role.role_id, i)
            UiManager:showUI("CharacterItemTip", {items = rewards, target = character_icon_box})
        end)
    end

    bee.addClick(self:find("character_main_unavailable", self.HeartLv1s[6]), function()
        Game:playSound("ui_button_confirm")
        self:onBtAwake()
    end)

    bee.addClick(self.AvailableButton, function()
        Game:playSound("ui_button_confirm")
        self:onBtAwake()
    end)

    bee.addClick(self.GiftButton, function()
        Game:playSound("ui_button_confirm")
        if self._selectGift.num <= 0 then
            if not ShopModel:autoShowCharacterGift(self._role.role_id) then
                UiManager:showUI("BackpackDetail", {data = self._selectGift, characterId = self._role.role_id})
            end
            return
        end
        if CharacterModel:getLeftGiftCnt() <= 0 and not self._lovesSpc[self._selectGift.item_id] then
            if not ShopModel:autoShowCharacterGift(self._role.role_id) then
                UiManager:showUI("CharacterGiftResult", {data = self._selectGift})
            end
            return
        end
        if self._selectGift.locked then
            if not ShopModel:autoShowCharacterGift(self._role.role_id) then
                UiManager:showUI("BackpackDetail", {data = self._selectGift, characterId = self._role.role_id})
            end
            return
        end
        if self._lovesSpc[self._selectGift.item_id] == 2 and LocalStore:isTagValid("character_bond_gift_prompt" .. PlayerModel:getUid()) then
            UiManager:showUI("CharacterMainPrompt", {
                data = self._selectGift,
                onSure = function()
                    Net:sendReq("pb.RoleGiftREQ", {
                        role_id = self._role.role_id,
                        item_uniq_id = self._selectGift.item_uniq_id,
                    })
                end
            })
        else
            Net:sendReq("pb.RoleGiftREQ", {
                role_id = self._role.role_id,
                item_uniq_id = self._selectGift.item_uniq_id,
            })
        end
    end)

    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipUD", {text = _F("LAB_GIFT_RULES_1", VipModel:getDailyGiftCounts()), target = self.InfoButton})
        bee.logEvent("character-bond-giftrules")
    end)
    bee.addClick(self:find("InfoButton", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonRules", {text = _T("LAB_BOND_RULES_1")})
        bee.logEvent("character-bond-rules")
    end)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:onBtClose()
        bee.emit(EventDef.evt_role_back_to_main, self.__cname)
    end, true)

    if bee.isDev then
        bee.addClick(self:find("Heart01", self.BondLevel), function()
            self:showBondsUpAnim()
        end)
    end

    self._stage = 0     -- 当前状态 0主界面 1bondsup 2awaken
end

function P:onShow()
    P.super.onShow(self)
    if not self._params then
        self._role = CharacterModel:getUsingRole()
    else
        self._role = self._params.data or self._datas[1]
    end
    if self._params and self._params.jump then
        if self._params.jump.select == 1 then
            -- 选中礼物
            if self._role:getBondLevel() >= Config.AWAKEN_LEVEL then
                -- 当前角色已满级
                for _, v in ipairs(self._datas) do
                    if CharacterModel:getRoleIsOwn(v.role_id) and v:getBondLevel() < Config.AWAKEN_LEVEL then
                        self._role = v
                        break
                    end
                end
            end
        elseif self._params.jump.select == 2 then
            -- 选中角色
            for _, v in ipairs(self._datas) do
                if v.role_id == self._params.jumpId then
                    self._role = v
                    break
                end
            end
        end
    end

    self:refreshLeftRight()

    self:refreshUI()
    
    self:playOpenAnim()
end

function P:onHide()
    P.super.onHide(self)
    if self.AwakenCls then
        self.AwakenCls:removeAutoEvent()
    end
    if self.BondsupCls then
        self.BondsupCls:removeAutoEvent()
    end
end

function P:playOpenAnim()
    if self._params and self._params.from == "Character" then
	    self._openAnim, self._closeAnim = nil, ""
    else
	    self._openAnim, self._closeAnim = nil, ""
    end
end

function P:refreshUI()
    P.super.refreshUI(self)

    self._loves = {}
    self._lovesSpc = {}
    for i = 1, #self._role.info.loves - 1, 2 do
        self._loves[self._role.info.loves[i]] = 1
    end
    for i = 1, #self._role.info.special - 1, 2 do
        self._lovesSpc[self._role.info.special[i]] = 2
    end

    local gifts = get_tpl_subKey(tpl_props_list, "type", GPropKind.Gift)
    self._gifts = {}
    for _, v in ipairs(gifts) do
        local d = ItemModel:getItem(v.id, true)
        if d then
            if d.num <= 0 and not self._loves[d.id] and d.quality <= GPropQuality.COLOR_4 then
            else
                table.insert(self._gifts, d)
                d.info = v
            end
        end
    end

    self:resortDatas()

    self._selectGift, self._selectItem = nil, nil
    local toIndex = nil
    -- 选中跳转道具
    if self._params and self._params.jump and self._params.jump.select == 1 then
        for k, v in ipairs(self._gifts) do
            if v.info.id == self._params.jumpId then
                self._selectGift = v
                toIndex = k
                break
            end
        end
    end

    self.GiftsList:setDatas(self._gifts)
    self:refreshInfos()
    -- self.GarmentsNotOwned:SetActive(self._role.locked)
    if toIndex then
        self.GiftsList:moveToYItem(toIndex)
    end

    self:refreshNoOwned()
    
    if self._role:isCanAwakenRed() then
        CharacterModel:removeAwakenRed(self._role.role_id)
    end
end

function P:resortDatas()
    table.sort(self._gifts, function(a, b)
        if a:isLocked() ~= b:isLocked() then
            return not a:isLocked()
        end
        if a.num == 0 and b.num ~= 0 then
            return false
        elseif a.num ~= 0 and b.num == 0 then
            return true
        end
        if self._loves[a.item_id] and self._loves[b.item_id] then
            if a.info.quality ~= b.info.quality then
                return a.info.quality > b.info.quality
            end
            if self._loves[a.item_id] ~= self._loves[b.item_id] then
                return self._loves[a.item_id] > self._loves[b.item_id]
            end
        elseif self._loves[a.item_id] or self._loves[b.item_id] then
            return self._loves[a.item_id] ~= nil
        end
        if a.info.quality ~= b.info.quality then
            return a.info.quality > b.info.quality
        end
        return a.item_id < b.item_id
    end)
end

function P:refreshInfos(isAmin)
    bee.setText(self.TextDailyLeft, _F("LAB_CHAR_053", CharacterModel:getLeftGiftCnt()))
    -- bee.setText(self.TextCurLevel, self._role:getBondLevelStr(tostring(Config.AWAKEN_LEVEL)))
    local showLvl = self._role:getBondLevel() <= Config.AWAKEN_LEVEL and self._role:getBondLevel() or Config.AWAKEN_LEVEL
    bee.setText(self.TextCurLevel, showLvl)
    bee.setText(self.TextCurLevel2, showLvl)
    self:find("Heart01/character_bond_level_heart_02", self.BondLevel):SetActive(self._role:isAwaken())
    self.TextCurLevel:SetActive(not self._role:isAwaken())
    self.TextCurLevel2:SetActive(self._role:isAwaken())
    local lvl = self._role:getBondLevel()
    local d = tpl_character_level[lvl]
    local val = self._bondProgress[lvl]
    local to = val
    if d and lvl < Config.AWAKEN_LEVEL then
        local point = d["point_" .. self._role.role_id] or d.point
        bee.setText(self.TextBondValue, _F("LAB_CHAR_050", self._role:getBondExp(), point))
        to = val + (self._bondProgress[lvl+1] - val) * (self._role:getBondExp() / point)
        self.TextBondTip:SetActive(true)
        self.TextBondFull:SetActive(false)
        self.character_bond_level_bg:SetActive(true)
    elseif 0 == lvl then
        self.character_bond_level_bg:SetActive(false)
    else
        bee.setText(self.TextBondValue, "")
        self.TextBondTip:SetActive(false)
        self.TextBondFull:SetActive(true)
        self.character_bond_level_bg:SetActive(true)
    end
    if to > self._bondProgress[#self._bondProgress - 1] then
        to = self._bondProgress[#self._bondProgress - 1]
    end
    if isAmin then
        bee.Tween.toFloat(self.character_bond_heart_line_fg.transform.sizeDelta.x, self._bondProgressSize.x * to, 0.2, function(v)
            self.character_bond_heart_line_fg.transform.sizeDelta = bee.v2(v, self._bondProgressSize.y)
        end)
    else
        self.character_bond_heart_line_fg.transform.sizeDelta = bee.v2(self._bondProgressSize.x * to, self._bondProgressSize.y)
    end
    
    self.character_bond_heart_line_oath_fg:SetActive(self._role:isAwaken())
    self.character_bond_heart_line_oath_bg:SetActive(not self._role:isAwaken())

    local c1, c2, c3 = bee.getColor(self:find("TEXT1", self.HeartLv1s[1])), COLOR.main_white, CU.Color(247/255, 251/255, 41/255)
    for i = 1, lvl do
        self:find("On", self.HeartLv1s[i]):SetActive(true)
        self:find("Off", self.HeartLv1s[i]):SetActive(false)
        if i <= Config.AWAKEN_LEVEL then
            self:find("character_icon_box/character_main_box_checkmark", self.HeartLv1s[i]):SetActive(true)
        end
    end
    for i = lvl + 1, #self.HeartLv1s do
        self:find("On", self.HeartLv1s[i]):SetActive(false)
        self:find("Off", self.HeartLv1s[i]):SetActive(true)
        if i <= Config.AWAKEN_LEVEL then
            self:find("character_icon_box/character_main_box_checkmark", self.HeartLv1s[i]):SetActive(false)
        end
    end
    -- if lvl >= 3 then
    --     self.HeartList:GetComponent("ScrollRect").horizontalNormalizedPosition = 1
    -- else
    --     self.HeartList:GetComponent("ScrollRect").horizontalNormalizedPosition = 0
    -- end

    if self._role:isAwaken() then
        self:find("character_main_pledged", self.HeartLv1s[6]):SetActive(true)
        self:find("character_main_unavailable", self.HeartLv1s[6]):SetActive(false)
    else
        self:find("character_main_pledged", self.HeartLv1s[6]):SetActive(false)
        self:find("character_main_unavailable", self.HeartLv1s[6]):SetActive(true)
    end
    self.character_bond_bg:SetActive(lvl < Config.AWAKEN_LEVEL)
    self.Pledged:SetActive(lvl > Config.AWAKEN_LEVEL)
    self.AvailableButton:SetActive(lvl == Config.AWAKEN_LEVEL)
    if lvl == Config.AWAKEN_LEVEL then
        local flag = self._role:isCanAwakenRed()
        self:find("Eff_poker_Ui_Awaken_light_loop", self.AvailableButton):SetActive(flag)
        self:find("eff_ks_qian", self.AvailableButton):SetActive(flag)
    end

    if not CharacterModel:getRole(self._role.role_id) then
        self.PackageButton:SetActive(false)
    elseif not self._role:isAwaken() and ShopModel:getCharacterGiftCfg(self._role.role_id) then
        self.PackageButton:SetActive(true)
    else
        self.PackageButton:SetActive(false)
    end
end

function P:setSelectData(data, item)
    if self._selectItem then
        self:find("common_item_grid_m_selected", self._selectItem):SetActive(false)
    end
    self._selectGift = data
    self._selectItem = item
    if self._selectItem then
        self:find("common_item_grid_m_selected", self._selectItem):SetActive(true)
    end
    -- self:refreshSelect()
end

function P:refreshGift(data, item)
    local cls = ObjectPool:getCls(item)
    if not cls then
        cls = PropItem:create(item, data)
    end
    cls:setData(data)
    self:find("character_bond_icon_heart", item):SetActive(self._loves[data.item_id])
    self:find("Locked", item):SetActive(data.num == 0)
    self:find("common_item_grid_m_selected", item):SetActive(data == self._selectGift)
    --if data.num == 0 then
        self:find("LinkTag", item):SetActive(false)
    --end

    if not self._selectGift then
        self:setSelectData(data, item)
    elseif data == self._selectGift then
        self._selectItem = item
    end
    if GuideManager:isInGuide() and data == self._gifts[1] then
        item.name = "Item1"
    end
    bee.addClick2(item, function()
        if GuideManager:isInGuide() then
            return
        end
        Game:playSound("ui_button_confirm")
        if self._selectGift == data then
            UiManager:showUI("BackpackDetail", {data = data, jumpCb = function(jumpId)
                bee.logEvent("character-bond-giftrecruitobtain")
                bee.logEvent("character-item_detail", data.item_id, jumpId)
            end, characterId = self._role.role_id})
        else
            self:setSelectData(data, item)
        end
    end, true)
end

function P:onBtAwake()
    if self._role:isAwaken() then
        return
    end
    UiManager:showUI("CharacterAwaken", {data = self._role, roleCanvas = self._RoleCanvas, hideCb = function()
        if not UiManager:getUI("CharacterOathFulfilled") then
            self:playAnimator("UI_1_CharacterMainBonds_return2")
            self:refreshRole()
        end
    end})
end

function P:evt_RoleGiftRSP(msg)
    P.super.evt_RoleGiftRSP(self, msg)
    self:refreshInfos(true)
    local item_id
    for _, v in ipairs(self._gifts) do
        if v.item_uniq_id == msg.item_uniq_id then
            item_id = v.item_id
            if v.num <= 0 then
                self:resortDatas()
                self._selectItem = nil
                self._selectGift = self._gifts[1]
                self.GiftsList:setDatas(self._gifts)
            else
                local item = self.GiftsList:getDataNode(v)
                if item then
                    self:refreshGift(v, item)
                end
            end
            break
        end
    end

    if self.LevelUpTips then
        local tips = CU.GameObject.Instantiate(self.LevelUpTips, self.Center.transform, false)
        tips:SetActive(true)
        bee.setText(self:find("TextTips", tips), _F("LAB_CHAR_062", msg.bond_change_rsp.bond_inc))
        bee.tween(tips)
        : by(1, {y = 100})
        : link()
        CU.GameObject.Destroy(tips, 1)
    end

    if msg.bond_change_rsp.bond_inc > msg.bond_change_rsp.bond_exp then
        self:showBondsUpAnim()
    else
        local chats = CharacterModel:getChats(not self._lovesSpc[item_id] and CHAT_VOICE_TYPE.Love1 or CHAT_VOICE_TYPE.Love2, msg.role_id)
        if chats then
            Game:playRoleOutVoice(msg.role_id, chats[1].key)
        end
    end
end

function P:showBondsUpAnim()
    self.ImageMask:SetActive(true)
    self:playAnimator("UI_1_CharacterMainBonds_back")
    self:once(0.325, function()
        AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_boundsup_big", UiManager:getUiRoot().transform, nil, 6, true)
        self:once(1.7, function()
            self.ImageMask:SetActive(false)
            UiManager:showUI("CharacterMainBondsUp", {data = self._role, hideCb = function()
                self:refreshRole()
                self:playAnimator("UI_1_CharacterMainBonds_return")
            end})
        end)
    end)
end

function P:evt_testBondsup()
    self:showBondsUpAnim()
end

-- function P:evt_SwitchRoleSkinRSP(msg)
--     self:refreshRole()
-- end

function P:evt_RoleAwakenRSP(msg)
    P.super.evt_RoleAwakenRSP(self, msg)
    self:refreshInfos()
end

function P:evt_ItemChangeRSP(msg)
    self:resortDatas()
    self.GiftsList:setDatas(self._gifts)
end

function P:evt_role_awakened_back_to_bonds()
    UiManager:showUI("CharacterItemsUnlocked", {items = CharacterModel:getRoleBondsRewards(self._role.role_id, Config.AWAKEN_LEVEL + 1), role = self._role})
    self:refreshRole()
end

function P:evt_uiManagerHideUI(uiName)
    if UiManager:isTopUI(self.node) then
        self:refreshRole()
    end
end

