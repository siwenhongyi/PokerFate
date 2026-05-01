local P = class("IngameAllin", UiBase)

function P:onAwake()
    self._closeAnim = ""
    self.Center = self:find("AnimRoot/Center")
    self.CharacterImage = self:find("CharacterImage", self.Center)
    self.RoleSpine = self:find("RoleSpine", self.Center)

    self.Player = self:find("Player", self.Center)
    self.ingame_history_player_01 = self:find("ingame_history_player_01", self.Player)
    self.ImageTitle = self:find("ImageTitle", self.Player)
    self.TextName = self:find("TextName", self.Player)
    self.TextLevel = self:find("Rank/TextLevel", self.Player)
end

function P:onShow()
    self:once(tpl_constdata.IngameAllinDt, function()
        self:hideUI()
    end)

    if self._params and self._params.role then
        if self._params.skin then
            bee.invoke(self.CharacterImage, "setSkin", self._params.skin, false, true)
        else
            bee.invoke(self.CharacterImage, "setRole", self._params.role, false, true)
        end
        bee.setTextCut(self.TextName, PlayerModel:getName(), 460)
        bee.setText(self.TextLevel, PlayerModel:getCurLevel())
        GF.setTitleImage(self.ImageTitle, PlayerModel:getTitle(), true, true)
        if PlayerModel:getCurLevel() > 0 then
            bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[PlayerModel:getCurLevel()].icon)
        end
        return
    end
    
	local player = GameModel.data:getPlayer(self._params and self._params.seatid or 1)
    local skin = tpl_character_skin[player and player.skin_id or 100401]
    if skin then
        bee.invoke(self.CharacterImage, "setSkin", skin, false, true)
    end

    bee.setTextCut(self.TextName, player.name, 460)
    bee.setText(self.TextLevel, player.level)
    GF.setTitleImage(self.ImageTitle, player.title, true, true)
    if player.level > 0 then
        bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[player.level].icon)
    end

    if player.uid == PlayerModel:getUid() then
        bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_01]")
	    bee.vibrate(tpl_vibrate.shock_allin)
    else
        if player.user_type == USER_TYPE.Developer then
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_04]")
        elseif player.user_type == USER_TYPE.Streamer then
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_03]")
        else
            bee.setIcon(self.ingame_history_player_01, "InGame[ingame_history_player_02]")
        end
    end
end

return P