local P = class("CharacterAwaken", UiFullView)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    P.super.onAwake(self)

    self:initUI()
end

function P:initUI()
    local AnimRoot = self:find("AnimRoot/Awaken") or self.node
    local Center = self:find("Center", AnimRoot)
    local RightTop = self:find("RightTop", AnimRoot)
    local RightBottom = self:find("RightBottom", AnimRoot)
    local LeftBottom = self:find("LeftBottom", AnimRoot)
    local LeftTop = self:find("LeftTop", AnimRoot)
    local Bottom = self:find("Bottom", AnimRoot)
    local AwakenMaterial = self:find("AwakenMaterial", Bottom)
    local Right = self:find("Right", AnimRoot)
    local AwakenReward = self:find("AwakenReward", Right)

    self.ImageMask = self:find("AnimRoot/ImageMask")
    self.CharacterImage = self:find("CharacterImage", Center)
    self.character_awaken_card = self:find("character_awaken_card", Center)
    self.ImageRole = self:find("character_awaken_card/card01/card02/Mask/ImageRole", Center)

    self.BgItems = self:find("BgItems", AwakenMaterial)
    self.Item1 = self:find("Item1", AwakenMaterial)
    self.Item1:SetActive(false)

    self.RewardItems = {
        self:find("item01", AwakenReward),
        self:find("item02", AwakenReward),
        self:find("item03", AwakenReward),
        self:find("item04", AwakenReward),
        self:find("item05", AwakenReward),
        self:find("item06", AwakenReward),
    }

    bee.addClick(self:find("BackButton", LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("LobbyButton", LeftTop), function()
        self:hideUI()
        UiManager:hideUI("CharacterMainBonds")
        UiManager:hideUI("CharacterMain")
    end)
    bee.addClick(self:find("InfoButton", LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonRules", {text = _T("LAB_BOND_RULES_1")})
        bee.logEvent("character-bond-rules")
    end)
    bee.addClick(self:find("AwakenButton", AwakenMaterial), function()
        Game:playSound("ui_button_confirm")
        local skin = self._role:getDefaultSkinData()
        bee.setIcon(self.ImageRole, skin.image, true)
        self.ImageRole.transform.localPosition = bee.v3(skin.card_offset[1], skin.card_offset[2])
        if skin.card_offset[3] then
            self.ImageRole.transform.localScale = bee.v3(skin.card_offset[3], skin.card_offset[3], skin.card_offset[3])
        else
            self.ImageRole.transform.localScale = bee.v3one
        end
        if self._role:getBondLevel() < Config.AWAKEN_LEVEL then
            UiManager:showToast(_T("LAB_CHAR_069"))
            if bee.isDev then
                self:doAwakeAnim()
            end
            return
        elseif self._role:getBondLevel() > Config.AWAKEN_LEVEL then
            UiManager:showToast(_T("LAB_CHAR_074"))
            if bee.isDev then
                self:doAwakeAnim()
            end
            return
        end
        local awaken = self:getAwakenItems()
        for i = 1, #awaken - 1, 2 do
            local d = ItemModel:getItem(awaken[i], true)
            if d.num < awaken[i + 1] then
                UiManager:showToast(_T("LAB_CHAR_070"))
                if bee.isDev then
                    self:doAwakeAnim()
                end
                return
            end
        end
        self._isInAwakening = true
        Net:sendReq("pb.RoleAwakenREQ", {
            role_id = self._role.role_id
        })
        -- self:hideUI()
    end)
    -- bee.addClick2(self.ImageExit, function()
    --     self.ImageExit:SetActive(false)
    --     self.parent._stage = 0
    --     self.parent.AnimRoot:GetComponent("PlayableDirector").enabled = false
    --     self.parent:playAnimator("UI_1_CharacterAwaken_back")
    -- end)
end

function P:onDestroy()
    if self._isPauseLobbyMusic then
        CS.SoundManager.Instance:UnPauseMusic()
        self._isPauseLobbyMusic = nil
    end
end

function P:initAwakenItems()
    if self.AwakenItems then
        for _, v in ipairs(self.AwakenItems) do
            CU.GameObject.Destroy(v)
        end
    end
    self.AwakenItems = {}
    local awaken = self:getAwakenItems()
    for i = 1, #awaken - 1, 2 do
        local item = CU.GameObject.Instantiate(self.Item1, self.BgItems.transform, false)
        item:SetActive(true)
        local d = ItemModel:getItem(awaken[i], true)
        PropItem:create(item, d):bindDetail(function()
            if d.type == GPropKind.PieceAwaken then
                bee.logEvent("character-oathdecorationfragment-detail")
            elseif d.type == GPropKind.PieceRole then
                bee.logEvent("character-oathplayerfragment-detail")
            end
        end, function(jumpId)
            if d.type == GPropKind.PieceAwaken then
                if jumpId == 2001 then
                    bee.logEvent("character-decorationfragment-recruitobtain")
                else
                    bee.logEvent("character-decorationfragment-shopobtain")
                end
            elseif d.type == GPropKind.PieceRole then
                if jumpId == 2001 then
                    bee.logEvent("character-playerfragment-recruitobtain")
                else
                    bee.logEvent("character-playerfragment-shopobtain")
                end
            end
            bee.logEvent("character-item_detail", d.item_id, jumpId)
        end)
        if d.num >= awaken[i + 1] then
            bee.setText(self:find("TextNum", item), "" .. _N(d.num) .. "/" .. _N(awaken[i + 1]))
        else
            bee.setText(self:find("TextNum", item), _F("LAB_CHAR_068", _N(d.num), _N(awaken[i + 1])))
        end
        table.insert(self.AwakenItems, item)
    end
end

function P:onShow()
    if self._params then
        self._role = self._params.data

        self._CharacterImage = self._params.roleCanvas:getRoleImage()
        self._CharacterImage.transform:SetParent(self.CharacterImage.transform, false)
    end
    self:initAwakenItems()

    local rewards = CharacterModel:getRoleBondsRewards(self._role.role_id, Config.AWAKEN_LEVEL + 1)
    for k, v in ipairs(self.RewardItems) do
        if rewards[k] then
            v:SetActive(true)
            local icon = nil
            if rewards[k] == GPropId.CharacterEmojiId then
                local emojis = get_tpl_subKey(tpl_emoji_list, "role", self._role.role_id)
                if emojis then
                    for _, v in ipairs(emojis) do
                        if v.unlock == Config.AWAKEN_LEVEL + 1 then
                            icon = v.emoji
                            break
                        end
                    end
                end
                bee.setIcon(self:find("Mask/ImageIcon", v), icon or tpl_props[rewards[k]].icon)
            else
                bee.setIcon(self:find("Mask/ImageIcon", v), tpl_props[rewards[k]].icon)
            end
            bee.addClick(v, function()
                Game:playSound("ui_button_confirm")
                UiManager:showUI("CommonItemTip", {data = tpl_props[rewards[k]], icon = icon, target = v})
            end)
        else
            v:SetActive(false)
        end
    end
end

function P:getAwakenItems()
    local datas = get_tpl_subKey(tpl_character_bond_list, "role", self._role.role_id)
    for _, v in ipairs(datas) do
        if v.awaken then
            return v.awaken
        end
    end
end

function P:doAwakeAnim()
    Game:pauseLobbyMusicTween()
    self._isPauseLobbyMusic = true
    self:once(tpl_constdata.Oath_BGM_Off, function()
        Game:playLobbyMusicTween()
        self._isPauseLobbyMusic = false
    end)

    Game:playSound("sound_oath")
    self:playAnimator("UI_1_CharacterAwaken_start")
    self.ImageMask:SetActive(true)
    bee.vibrate(tpl_vibrate.shock_pledge_start)
    self:once(1.6, function()
        bee.vibrate(tpl_vibrate.shock_pledge_card)
    end)
    self:once(10, function()
        bee.vibrate(tpl_vibrate.shock_pledge_finish)
    end)
    
    self:once(4.35, function()
        local to = self.character_awaken_card.transform.position
        for k, v in ipairs(self.AwakenItems) do
            local p1 = v.transform.position
            AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_awaken_cl_bf", self.node.transform, nil, 1)
            .transform.position = p1
            local dt = 0.6 + (k - 1) * 0.1
            local eft = AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_awaken_cl_trail", self.node.transform, nil, dt + 0.9)
            eft.transform.position = p1
            local center = bee.v3(p1.x + 3 * (k % 2 == 1 and -1 or 1), (p1.y + to.y) / 2)
            local cmp = CS.BezierAction.BezierTo(eft, eft.transform.position, center, to, dt)
            cmp.isLocal = false
            cmp:OnComplete(function()
                AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_awaken_cl_zr", self.node.transform, nil, 1).transform.position = to
            end)
        end
        for k, v in ipairs(self.AwakenItems) do
            v:SetActive(false)
        end
    end)
    self:once(8.5, function()
        local skin = self._role:getAwakenSkinData()
        bee.setIcon(self.ImageRole, skin.image_with_bg or skin.image, true)
        self.ImageRole.transform.localPosition = bee.v3(skin.card_offset[1], skin.card_offset[2])
        if skin.card_offset[3] then
            self.ImageRole.transform.localScale = bee.v3(skin.card_offset[3], skin.card_offset[3], skin.card_offset[3])
        else
            self.ImageRole.transform.localScale = bee.v3one
        end
        -- self.parent:refreshRole()
    end)
    self:once(10.5, function()
        UiManager:showUI("CharacterOathFulfilled", {data = self._role})
        -- self.ImageExit:SetActive(true)
        -- bee.setText(self:find("Tips/TextTip", self.ImageExit), _T(self._role.info.awaken_tip))
        -- Game:playRoleOutVoice(self._role.role_id, tpl_chat_voice.awaken)

        SdkHelper:startAppReview()
    end)
    self:once(12, function()
        self:hideUI()
    end)
end

function P:evt_RoleAwakenRSP(msg)
    -- UiManager:showToast(_T("LAB_CHAR_073"))
    self:doAwakeAnim()
end

function P:evt_item_refresh()
    if not self._isInAwakening then
        local awaken = self:getAwakenItems()
        for k, item in ipairs(self.AwakenItems) do
            local i = (k - 1) * 2 + 1
            local d = ItemModel:getItem(awaken[i], true)
            if d.num >= awaken[i + 1] then
                bee.setText(self:find("TextNum", item), "" .. _N(d.num) .. "/" .. _N(awaken[i + 1]))
            else
                bee.setText(self:find("TextNum", item), _F("LAB_CHAR_068", _N(d.num), _N(awaken[i + 1])))
            end
        end
    end
end

