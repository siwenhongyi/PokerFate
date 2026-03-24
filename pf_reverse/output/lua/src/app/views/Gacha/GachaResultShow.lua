local P = class("GachaResultShow", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	self.Center = self:find("Center", self.AnimRoot)
	self.RightTop = self:find("RightTop", self.AnimRoot)
	self.LeftTop = self:find("LeftTop", self.AnimRoot)

	self.ItemCont = self:find("ItemCont", self.Center)
	self.ItemCont:SetActive(false)
	self.ItemIcon = self:find("ItemIcon", self.ItemCont)
	self.NameText = self:find("NameText", self.ItemCont)
	self.ItemNew = self:find("ItemNew", self.ItemCont)
	self.itemBgList = {}
	for i = 1, 4 do
		self.itemBgList[i] = self:find("ItemBg" .. i, self.ItemCont)
	end

	self.RoleCont = self:find("RoleCont", self.Center)
	self.RoleCont:SetActive(false)
	self.CampIcon = self:find("CampIcon", self.RoleCont)
	self.RoleImg = self:find("RoleImg", self.RoleCont)
	self.CVNameText = self:find("CVNameText", self.RoleCont)
	self.RoleNameText = self:find("RoleNameText", self.RoleCont)
	self.NewIcon = self:find("NewIcon", self.RoleCont)
	self.TipsText = self:find("TipsText/TipsText", self.RoleCont)
	self.TipsTextPos = self:find("TipsText/TipsTextPos", self.RoleCont)

	self.SkinCont = self:find("SkinCont", self.Center)
	self.SkinImage = self:find("CharacterImage", self.SkinCont)
	self.SkinNameText = self:find("LeftBottom/NameCard/SkinNameText", self.SkinCont)
	self.SkinRoleNameText = self:find("LeftBottom/NameCard/NameText", self.SkinCont)
	self.WearButton = self:find("RightBottom/WearButton", self.SkinCont)
	self.DressedText = self:find("RightBottom/DressedText", self.SkinCont)
	self.BackButton = self:find("LeftTop/BackButton", self.SkinCont)
	self.DressedText:SetActive(false)
	
	self.ShareCont = self:find("ShareCont", self.LeftTop)
	self.ShareButton = self:find("ShareButton", self.ShareCont)
	self.ShareReward = self:find("ShareReward", self.ShareCont)

	self.SkipButton = self:find("SkipButton", self.RightTop)

	self.ItemCont:SetActive(false)
	self.RoleCont:SetActive(false)
	self.SkinCont:SetActive(false)

	self.ClickMask = self:find("ClickMask", self.AnimRoot)
	bee.addClick(self.ClickMask, function()
		self:onClickNext()
	end)
	bee.addClick(self.BackButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickNext()
	end)

	bee.addClick(self.SkipButton, function()
		if bee.checkCd("gacharesult_skip", 1) then
			Game:playSound("ui_button_confirm")
			self:onClickSkipButton()
		end
	end)

	bee.addClick(self.ShareButton, function()
		UiManager:showUI("ShareMain", {id = 2})
	end)

	self.ShareCont:SetActive(not GuideManager:isInGuide())
	self.RightTop:SetActive(not GuideManager:isInGuide())
end

function P:onStart()
	self._showCount = #self._params.showList
	self._showList = self._params.showList
	self._curShow = table.remove(self._showList, 1)
	self:setCurShow()
end

function P:setCurShow()
	bee.stopVoice()
	Game:stopRoleSound()

	if self._curShow.major_type == GMajorType.ROLE then
		self:setCharacterShow()
		self.ShareButton:SetActive(true)
		self:setShareCont()
	elseif self._curShow.major_type == GMajorType.ROLE_SKIN then
		self:setSkinShow()
		self.ShareButton:SetActive(false)
		self.ShareReward:SetActive(false)
	else
		self.ShareButton:SetActive(false)
		self.ShareReward:SetActive(false)
		self:setItemShow()
	end
	if self._showCount == 1 then
		self.SkipButton:SetActive(false)
	elseif not self._curShow.new and self._curShow.major_type ~= GMajorType.ROLE then
		self.SkipButton:SetActive(true)
	else
		self.SkipButton:SetActive(false)
	end
end

function P:setCharacterShow()
	self._isShowCharacter = true
	self.ClickMask:SetActive(false)
	Game:playSound("sound_recruit_character")
	self:showAnim(self.RoleCont, function()

		local id = self._curShow.id or self._curShow.item_id

		self.NewIcon:SetActive(self._curShow.new)

		local roleCfg = tpl_character[id]
		if not self.characterCls then
        	self.characterCls = ObjectPool:getCls(self.RoleImg)
        	self.characterCls:createRoleCanvas()
        end
        self.characterCls:setRole(CharacterModel:getRoleData(roleCfg.id, true))
    	-- 默认皮肤
    	local skins = get_tpl_subKey(tpl_character_skin_list, "role", roleCfg.id)
    	self.characterCls:setSkin(skins[1])

		bee.setIconInAtlas(self.CampIcon, roleCfg.camp, true)
		bee.setText(self.RoleNameText, _T(roleCfg.name))
		bee.setText(self.CVNameText, "CV:" .. _T(roleCfg.cv))
		bee.setText(self.TipsText, "")

		self._showText = _T(roleCfg.salute)
		bee.setText(self.TipsTextPos, self._showText)

		self:once(1.8, function()
			bee.vibrate(tpl_vibrate.shock_character)
		end)
		self:once(3.5, function()
			local r = self.TipsTextPos.transform.rect
			self.TipsText.transform.sizeDelta = bee.v2(r.width, r.height)

			self:showTextCont()
			Game:playRoleOutVoice(roleCfg.id, roleCfg.salute_voice)
			self.ClickMask:SetActive(true)
		end)
	end)
end

function P:showTextCont()
	self._textList = self:getShowTextList(self._showText)
	self._textLen = self:getTextListLen()

	local index = 0
	self._typeWriterTag = self:schedule(0.08, function()
		index = index + 1
		if index > self._textLen then
			scheduler:removeTag(self._typeWriterTag)
			self._typeWriterTag = nil
		else
			bee.setText(self.TipsText, self:getTextListSub(index))
		end
	end)
end

function P:getTextListLen()
    local ret = 0
    for _, v in ipairs(self._textList) do
        if v.text then
            ret = ret + string.utf8len(v.text)
        end
    end
    return ret
end

function P:getTextListSub(index)
    local ret = ""
    for _, v in ipairs(self._textList) do
        if v.text then
            local len = string.utf8len(v.text)
            if index <= len then
                ret = ret .. (v.tag1 or "") .. string.utf8sub(v.text, 0, index) .. (v.tag2 or "")
                break
            else
                index = index - len
                ret = ret .. (v.tag1 or "") .. v.text .. (v.tag2 or "")
            end
        end
    end
    return ret
end

function P:setSkinShow()
	self.ClickMask:SetActive(false)
	self:showAnim(self.SkinCont, function()
		local id = self._curShow.id or self._curShow.item_id
		local skinCfg = tpl_character_skin[id]
		local roleCfg = tpl_character[skinCfg.role]

		bee.setText(self.SkinNameText, _T(skinCfg.name))
		bee.setText(self.SkinRoleNameText, _T(roleCfg.name))

		if not self.skinCharacterCls then
			self.skinCharacterCls = ObjectPool:getCls(self.SkinImage)
		end
		self.skinCharacterCls:setRole(CharacterModel:getRoleData(roleCfg.id, true), true)
		self.skinCharacterCls:setSkin(skinCfg, true)

		if not CharacterModel:getRole(roleCfg.id) then
			self.WearButton:SetActive(false)
		end

		bee.removeAllClick(self.WearButton)
		bee.addClick(self.WearButton, function()
			Game:playSound("ui_button_confirm")
	        Net:sendReq("pb.SwitchRoleSkinREQ", {
	            role_id = skinCfg.role,
	            new_skin_id = skinCfg.id,
	        })
			self.WearButton:SetActive(false)
			self.DressedText:SetActive(true)
		end)
	end)
end

function P:setItemShow()
	Game:playSound("sound_recruit_item")
	self._isShowCharacter = false
	self:showAnim(self.ItemCont, function()
		if not self._curShow then
			self:onClickClose()
			return
		end
		local cfg = tpl_props[self._curShow.id or self._curShow.item_id]
		for i = 1, 4 do
			self.itemBgList[i]:SetActive(i == cfg.quality)
		end
		if cfg.type == GPropKind.Table then
			local decoCfg = tpl_card_table[cfg.mapId]
			bee.setIconInAtlas(self.ItemIcon, decoCfg.bg_small, true)
			bee.setText(self.NameText, _F("LAB_PROPS_TEXT_7", _T("LAB_PROPS_TYPE_NAME_206"), _T(cfg.name)))
		elseif cfg.type == GPropKind.LobbyScene then
			local decoCfg = tpl_hall_scene[cfg.mapId]
			bee.setIconInAtlas(self.ItemIcon, decoCfg.bg_small, true)
			bee.setText(self.NameText, _F("LAB_PROPS_TEXT_7", _T("LAB_PROPS_TYPE_NAME_209"), _T(cfg.name)))
		elseif cfg.type == GPropKind.Title then
			bee.setIconInAtlas(self.ItemIcon, cfg.icon, true)
			bee.setText(self.NameText, _F("LAB_PROPS_TEXT_7", _T("LAB_PROPS_TYPE_NAME_204"), _T(cfg.name)))
		elseif cfg.type == GPropKind.AllInEff then
			local decoCfg = tpl_all_in_anim[cfg.mapId]
			bee.setIconInAtlas(self.ItemIcon, decoCfg.bg_small, true)
			bee.setText(self.NameText, _F("LAB_PROPS_TEXT_7", _T("LAB_PROPS_TYPE_NAME_210"), _T(cfg.name)))
		elseif cfg.type == GPropKind.NameplateEff then
			local decoCfg = tpl_nameplate_anim[cfg.mapId]
			bee.setIconInAtlas(self.ItemIcon, decoCfg.bg_small, true)
			bee.setText(self.NameText, _F("LAB_PROPS_TEXT_7", _T("LAB_PROPS_TYPE_NAME_211"), _T(cfg.name)))
		else
			bee.setIconInAtlas(self.ItemIcon, cfg.icon, true)
			bee.setText(self.NameText, _T(cfg.name))
		end
		self.ItemNew:SetActive(self._curShow.new)
	end)
end

function P:showAnim(showRoot, cb)
	local finishCb = function()
		if not self._curShow then
			self:onClickClose()
			return
		end
		if bee.isNull(self.node) then
			return
		end
		showRoot:SetActive(true)
		if cb then
			cb()
		end
	end

	if self._animTimeTag then
		scheduler:removeTag(self._animTimeTag)
		self._animTimeTag = nil
	end

	if self.RoleCont.activeSelf then
		local animator = self.RoleCont:GetComponent("Animator")
		local time = CS.AnimatorManager.Instance:GetAnimationTimes(animator, "UI_1_RoleCont_back")
		animator:Play("UI_1_RoleCont_back", -1, 0)
		self._animTimeTag = self:once(time, function()
			self.RoleCont:SetActive(false)
			finishCb()
		end)
	elseif self.ItemCont.activeSelf then
		local animator = self.ItemCont:GetComponent("Animator")
		local time = CS.AnimatorManager.Instance:GetAnimationTimes(animator, "UI_2_IthemCont_back")
		animator:Play("UI_2_IthemCont_back", -1, 0)
		self._animTimeTag = self:once(time, function()
			self.ItemCont:SetActive(false)
			finishCb()
		end)
	elseif self.SkinCont.activeSelf then
		self.SkinCont:SetActive(false)
		finishCb()
	else
		finishCb()
	end
end

function P:onClickNext()
	if not bee.checkCd("CommonNewRewards_onClickNext", 1) then
		return
	end

	if self._isShowCharacter and self._typeWriterTag then
		scheduler:removeTag(self._typeWriterTag)
		self._typeWriterTag = nil

		bee.setText(self.TipsText, self._showText)
		return
	end

	self._curShow = table.remove(self._showList, 1)
	if not self._curShow then
		self:onClickClose()
		return
	end

	self:setCurShow()
end

function P:onClickSkipButton()
	local newList = {}
	for i, v in ipairs(self._showList) do
		if v.new or v.major_type == GMajorType.ROLE then
			table.insert(newList, v)
		end
	end
	self._showList = newList
	self._curShow = table.remove(self._showList, 1)
	if self._curShow then
		self:setCurShow()
	else
		self:onClickClose()
	end
end

function P:onClickClose()
	if self.RoleCont.activeSelf then
		self.RoleCont:GetComponent("Animator"):Play("UI_1_RoleCont_back")
	end
	if self.ItemCont.activeSelf then
		self.ItemCont:GetComponent("Animator"):Play("UI_2_IthemCont_back")
	end

	self._closeAnim = ""
	if self._params.closeCb then
		self._params.closeCb()
	end
	self:once(0.5, function()
		if self._playingVoice then
			bee.stopVoice("")
			Game:stopRoleSound()
			self._playingVoice = nil
		end
		self:hideUI(nil, true)
	end)
end

function P:evt_shareShot()
	self.SkipButton:SetActive(false)
    self.ShareCont:SetActive(false)
end

function P:evt_endShareShot()
	self.SkipButton:SetActive(true)
    self.ShareCont:SetActive(true)
end

function P:evt_updateSharedPage()
    self:setShareCont()
end

function P:setShareCont()
    local Icon = self:find("Icon", self.ShareReward)
    local CountText = self:find("CountText", self.ShareReward)
    ShareModel:setShareCont(self.ShareReward, Icon, CountText, 2)
end

-- 获取对话文本的富文本显示列表
function P:getShowTextList(text)
    local textList = {}

    local i, textStart = 1, 1
    while i <= #text do
        if string.byte(text, i) == 60 then
            local j = string.find(text, ">", i)
            if j then
                if textStart < i then
                    table.insert(textList, {text = string.sub(text, textStart, i - 1)})
                end
                local tag = string.sub(text, i, j)
                if string.byte(text, i + 1) == 47 then
                    local tagName = string.sub(tag, 3, -2)
                    table.insert(textList, {tag2 = tag, tagName = tagName})
                else
                    local tagName = string.sub(tag, 2, string.find(tag, "=") - 1)
                    table.insert(textList, {tag1 = tag, tagName = tagName})
                end
                i = j + 1
                textStart = i
            else
                i = i + 1
            end
        else
            i = i + 1
        end
    end
    if textStart < #text then
        table.insert(textList, {text = string.sub(text, textStart)})
    end
    local function parseTag(retList, dom, textList, idx, parentTags)
        local v = textList[idx]
        if not v then
            return
        end
        if not parentTags then
            parentTags = {}
        end
        if v.text then
            if not dom or dom.text then
                dom = {}
                retList[#retList + 1] = dom
            end
            dom.text = v.text
            return parseTag(retList, dom, textList, idx + 1, parentTags)
        elseif v.tag1 then
            local newDom = {
                tag1 = "",
                tagName = v.tagName,
            }
            for _, tv in ipairs(parentTags) do
                newDom.tag1 = newDom.tag1 .. tv.tag1
            end
            newDom.tag1 = newDom.tag1 .. v.tag1
            retList[#retList + 1] = newDom
            for i = idx + 1, #textList do
                local nv = textList[i]
                if nv.tag2 and nv.tagName == v.tagName then
                    newDom.tag2 = nv.tag2
                    for i = #parentTags, 1, -1 do
                        newDom.tag2 = newDom.tag2 .. parentTags[i].tag2
                    end
                    parentTags[#parentTags + 1] = {tag1 = v.tag1, tag2 = nv.tag2, tagName = v.tagName}
                    break
                end
            end
            return parseTag(retList, newDom, textList, idx + 1, parentTags)
        elseif v.tag2 then
            for i = #parentTags, 1, -1 do
                if parentTags[i].tagName == v.tagName then
                    table.remove(parentTags, i)
                    break
                end
            end
            return parseTag(retList, dom, textList, idx + 1, parentTags)
        end
        return idx + 1
    end
    
    local retList = {}
    parseTag(retList, nil, textList, 1)
    return retList
end

