local PKHelper = require("app.table.PK.PKHelper")
local P = class("IngameResult", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    
    self.Center = self:find("AnimRoot/Center")
    self.TextCardType = self:find("TextCardType", self.Center)
    self.BgTitle = self:find("BgTitle", self.Center)
    self.BgInfo = self:find("BgInfo", self.Center)
    self.ImageCards = {
        self:find("ImageCard1", self.BgInfo),
        self:find("ImageCard2", self.BgInfo),
        self:find("ImageCard3", self.BgInfo),
        self:find("ImageCard4", self.BgInfo),
        self:find("ImageCard5", self.BgInfo),
    }
    self.TextChip = self:find("Chip/TextChip", self.BgInfo)
    self.BgReward = self:find("BgReward", self.Center)
    self.Item1 = self:find("Item1", self.BgReward)
    self.Item1:SetActive(false)
    self.Player = self:find("Player", self.Center)
    self.ingame_history_player_01 = self:find("ingame_history_player_01", self.Player)
    self.ImageTitle = self:find("ImageTitle", self.Player)
    self.TextName = self:find("TextName", self.Player)
    self.TextLevel = self:find("Rank/TextLevel", self.Player)
    self.CharacterImage = self:find("CharacterImage", self.Center)

    self.SaveButton = self:find("SaveButton", self.Center)
    bee.addClick2(self:find("Tips", self.SaveButton), function()
        self:find("Tips", self.SaveButton):SetActive(false)
    end)
    bee.addClick(self.SaveButton, function()
        GameModel.data:saveRecord(_T("LAB_SAVE_GAME_TIP3"))
        self.SaveButton:SetActive(false)
        bee.logEvent("ingame-hand-replay", GameModel.data:getGameType(), GameModel.data:getRoomId(), 2)
    end)
end

function P:onShow()
    bee.emit("evt_gameBlur", true, self.__cname)
    if GameModel.data then
        self:once(tpl_constdata.IngameResultDt, function()
            self:hideUI()
        end)

        local chipIcon = GameModel.data:getChipIcon()
        if chipIcon then
            bee.setIcon(self:find("Chip/ingame_result_chip", self.BgInfo), chipIcon)
        end
    end
    for _, v in ipairs(self.ImageCards) do
        bee.setIcon(v, GF.getCardImageByCode(0))
    end

	local boards = self._params.boards or GameModel.data:getBoardInfo()
	local player = self._params.player or GameModel.data:getPlayer(self._params.seatid)
	local cards, cardType, pkType = PKHelper.getCardType(self._params.hand_cards or player.hand_cards, boards, GameModel.data and GameModel.data:getRoomType() or GAME_GAME_TYPE.LOBBY_HOLDEM_GAME)
    -- bee.setText(self.TextCardType, _T(cardType))
    if not cards then
        self:once(-1, function()
            self:hideUIForce()
        end)
    end
    
    local c = cards and cards[1].color or 1
    if cardType == "LAB_HIGH_CARD" then
        self:showTitleNormal("highcard")
    elseif cardType == "LAB_ONE_PAIR" then
        self:showTitleNormal("onepair")
    elseif cardType == "LAB_TWO_PAIRS" then
        self:showTitleNormal("twopair")
    elseif cardType == "LAB_THREE_KIND" then
        self:showTitleNormal("threeofakind")
    elseif cardType == "LAB_STRAIGHT" then
        self:showTitleNormal("straight")
    elseif cardType == "LAB_FLUSH" then
        self:showTitleNormal("flush")
    elseif cardType == "LAB_FULL_HOUSE" then
        local title = bee.createObj("views/table/PKTitle/TitleFullhouse")
        title.transform:SetParent(self.BgTitle.transform, false)
        title.transform.localPosition = bee.v3zero
        for _, v in ipairs(Config.Languages) do
            self:find(v, title):SetActive(v == LAN:getLanguage())
        end
    elseif cardType == "LAB_QUADS" then
        local title = bee.createObj("views/table/PKTitle/TitleFourkind")
        title.transform:SetParent(self.BgTitle.transform, false)
        title.transform.localPosition = bee.v3zero
    elseif cardType == "LAB_STRAIGHT_FLUSH" then
        local title = bee.createObj("views/table/PKTitle/TitleStraighatflush")
        title.transform:SetParent(self.BgTitle.transform, false)
        title.transform.localPosition = bee.v3zero
        for _, v in ipairs(Config.Languages) do
            local lanNode = self:find(v, title)
            lanNode:SetActive(v == LAN:getLanguage())
            if v == LAN:getLanguage() and lanNode then
                for kk, vv in ipairs({"cm_dianmond", "cm_club", "cm_hreat", "cm_spade"}) do
                    self:find(vv, lanNode):SetActive(kk == c)
                end
            end
        end
        local colors = {"diamond", "club", "heart", "spade"}
        for k, v in ipairs(colors) do
            self:find(v, title):SetActive(k == c)
            self:find("ingame_result_title_straightflush_bg_" .. v .. "_mask", title):SetActive(k == c)
        end
    elseif cardType == "LAB_ROYAL_FLUSH" then
        local title = bee.createObj("views/table/PKTitle/TitleRoyalflush")
        title.transform:SetParent(self.BgTitle.transform, false)
        title.transform.localPosition = bee.v3zero
        for _, v in ipairs(Config.Languages) do
            local lanNode = self:find(v, title)
            lanNode:SetActive(v == LAN:getLanguage())
            if v == LAN:getLanguage() and lanNode then
                for kk, vv in ipairs({"cm_diamond", "cm_clob", "cm_heart", "cm_spade"}) do
                    self:find(vv, lanNode):SetActive(kk == c)
                end
            end
        end
        local colors = {"diamond", "club", "heart", "spade"}
        for k, v in ipairs(colors) do
            self:find(v, title):SetActive(k == c)
            self:find("ingame_result_title_royalflush_bg_" .. v .. "_mask", title):SetActive(k == c)
        end
    end

    if player.uid == PlayerModel:getUid() then
        bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_01]")
	    bee.vibrate(tpl_vibrate.shock_win)
    else
        if player.user_type == USER_TYPE.Developer then
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_04]")
        elseif player.user_type == USER_TYPE.Streamer then
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_03]")
        else
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_02]")
        end
    end
    bee.setText(self.TextChip, _N(self._params.chips))
    bee.setTextCut(self.TextName, player.name, 420)
    bee.setText(self.TextLevel, player.level)
    GF.setTitleImage(self.ImageTitle, player.title, true, true)
    if player.level > 0 then
        bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[player.level].icon)
    end
    local skin = tpl_character_skin[player.skin_id]
    if skin then
        bee.invoke(self.CharacterImage, "setSkin", skin, false, true)
        -- if cardType == "LAB_HIGH_CARD" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.high_card)
        -- elseif cardType == "LAB_ONE_PAIR" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.one_pair)
        -- elseif cardType == "LAB_TWO_PAIRS" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.two_pairs)
        -- elseif cardType == "LAB_THREE_KIND" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.three_of_a_kind)
        -- elseif cardType == "LAB_STRAIGHT" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.straight)
        -- elseif cardType == "LAB_FLUSH" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.flush)
        -- elseif cardType == "LAB_FULL_HOUSE" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.full_house)
        -- elseif cardType == "LAB_QUADS" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.four_of_a_kind)
        -- elseif cardType == "LAB_STRAIGHT_FLUSH" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.straight_flush)
        -- elseif cardType == "LAB_ROYAL_FLUSH" then
        --     Game:playRoleInVoice(skin.role, ROLE_VOICE.royal_flush)
        -- end
        Game:playRoleInVoice(skin.role, ROLE_VOICE.win)
    end
    if player.uid == PlayerModel:getUid() then
        self.BgReward:SetActive(true)
        local msg = self._params.msg or {}
        local rewards = {{GPropId.FirePower, msg.fire_power}, {GPropId.Exp, msg.win_exp}, {GPropId.Bond, msg.bond_add}}
        for _, v in ipairs(rewards) do
            if v[2] and v[2] > 0 then
                local item = ItemModel:getItem(v[1], true)
                item.num = v[2]
                local itemNode = CU.GameObject.Instantiate(self.Item1, self.BgReward.transform, false)
                itemNode:SetActive(true)
                PropItem:create(itemNode, item)
            end
        end
        self.BgInfo.transform.localPosition = bee.v3zero
    else
        self.BgReward:SetActive(false)
        self.BgInfo.transform.localPosition = bee.v3(0, -90)
    end

    self.SaveButton:SetActive(false)
    if not GuideManager:isInGuide() and GameModel.data then
        self:once(-1, function()
            if GameModel.data and GameModel.data:isCanSaveRecord() then
                self.SaveButton:SetActive(true)
                if player:isMe() then
                    local winType = GameModel.data:getWinType()
                    if winType >= 1 then
                        bee.setText(self:find("Tips/TextTips", self.SaveButton), _T("LAB_DEL_PLAYBACK_TIP2"))
                    else
                        bee.setText(self:find("Tips/TextTips", self.SaveButton), _T("LAB_DEL_PLAYBACK_TIP1"))
                    end
                else
                    self:find("Tips", self.SaveButton):SetActive(false)
                end
            end
        end)
    end

	if cards then
        cards = PKHelper.getSortCards(cards)
        for k, v in ipairs(cards) do
            bee.setIcon(self.ImageCards[k], GF.getCardImageByCode(GF.getCardCode(v.number, v.color)))
        end
	end
end

function P:preHide()
    P.super.preHide(self)
    bee.emit("evt_gameBlur", false, self.__cname)
end

function P:showTitleNormal(name)
    local title = bee.createObj("views/table/PKTitle/TitleNormal")
    title.transform:SetParent(self.BgTitle.transform, false)
    title.transform.localPosition = bee.v3zero
    local names = {"highcard", "onepair", "twopair", "threeofakind", "straight", "flush"}
    for _, v in ipairs(names) do
        self:find(v, title):SetActive(v == name)
    end
end

return P