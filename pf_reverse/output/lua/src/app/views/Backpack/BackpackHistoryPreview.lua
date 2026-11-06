local P = class("BackpackHistoryPreview", UiDialog)

function P:onAwake()
    self.MaskButton = self:find("AnimRoot/common_panel_mask_70")
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.CloseButton = self:find("CloseButton", self.Panel)
    self.HistoryList = self:find("HistoryList", self.Panel)
    self.PublicCards = {}
    self.PublicCardRoot = self:find("Viewport/Content/Public", self.HistoryList)
    for i = 1, 5 do
        local card = self:find("ImageCard" .. i , self.PublicCardRoot)
        table.insert(self.PublicCards, card)
    end
    self.PlayerName = self:find("Item/TextName", self.HistoryList)
    self.RankIcon = self:find("Item/Rank/icon_rank_01", self.HistoryList)
    self.Avatar = self:find("Item/Mask/ImageIcon", self.HistoryList)
    self.AvatarFrame = self:find("Item/ImageFrame", self.HistoryList)
    self.TitleIcon = self:find("Item/ImageTitle", self.HistoryList)
    self.OwnCards = {}
    self.OwnCardRoot = self:find("Item/BgCard2", self.HistoryList)
    for i = 1, 2 do
        local card = self:find("ImageCard" .. i , self.OwnCardRoot)
        table.insert(self.OwnCards, card)
    end

    bee.addClick(self.MaskButton, function ()
        self:hideUI()
    end)
    bee.addClick(self.CloseButton, function ()
        self:hideUI()
    end)
end

function P:onShow()
    if self._params == nil then
        self:hideUI()
    end
    self.scheme = self._params.scheme
    self:refreshDecoration()
end

function P:refreshDecoration()
    --级别
    bee.setIcon(self.RankIcon, tpl_level[PlayerModel:getCurLevel()].icon)
    --名称
    local width = self.PlayerName.transform.sizeDelta.x
    bee.setTextCut(self.PlayerName, PlayerModel:getNameIngame(), width)
    --头像
    bee.setIcon(self.Avatar, tpl_props[self.scheme.avatar].icon)
    --头像框
    if self.scheme.frame == nil or self.scheme.frame == 0 then
        self.AvatarFrame:SetActive(false)
    else
        self.AvatarFrame:SetActive(true)
        bee.setIcon(self.AvatarFrame, tpl_props[self.scheme.frame].icon)
    end
    --称号
    if self.scheme.title == nil or self.scheme.title == 0 then
        self.TitleIcon:SetActive(false)
    else
        self.TitleIcon:SetActive(true)
        bee.setIcon(self.TitleIcon, tpl_props[self.scheme.title].icon)
    end
    --牌面
    --local cardStr = tpl_card[self.scheme.card_front].image
    bee.setIcon(self.PublicCards[1], GF.getCardImage("10", "s", self.scheme))
    bee.setIcon(self.PublicCards[2], GF.getCardImage("j", "s", self.scheme))
    bee.setIcon(self.PublicCards[3], GF.getCardImage("q", "s", self.scheme))
    bee.setIcon(self.PublicCards[4], GF.getCardImage("k", "s", self.scheme))
    bee.setIcon(self.PublicCards[5], GF.getCardImage("a", "s", self.scheme))
    --牌背
    local backMapId = tpl_props[self.scheme.card_back].mapId
    local backIcon = tpl_card_back[backMapId].image
    bee.setIcon(self.OwnCards[1], backIcon)
    bee.setIcon(self.OwnCards[2], backIcon)

end

return P