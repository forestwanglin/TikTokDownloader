-- TikTokDownloader MySQL Schema
-- 用于存储爬取的抖音数据

CREATE DATABASE IF NOT EXISTS `spider_douyin`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `spider_tiktok`;

-- 作品数据表
CREATE TABLE IF NOT EXISTS `spider_tiktok_note` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `note_id` VARCHAR(64) NOT NULL COMMENT 'aweme_id，作品唯一标识',
    `note_url` VARCHAR(1024) DEFAULT NULL COMMENT '分享链接',
    `note_type` VARCHAR(32) DEFAULT NULL COMMENT 'video / image / live',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT 'uid / sec_uid',
    `home_url` VARCHAR(1024) DEFAULT NULL COMMENT '作者主页链接',
    `nickname` VARCHAR(255) DEFAULT NULL COMMENT '作者昵称',
    `avatar` VARCHAR(1024) DEFAULT NULL COMMENT '头像URL',
    `title` VARCHAR(512) DEFAULT NULL COMMENT '标题（desc第一行）',
    `desc` TEXT DEFAULT NULL COMMENT '完整描述',
    `liked_count` INT DEFAULT 0 COMMENT '点赞数 (digg_count)',
    `collected_count` INT DEFAULT 0 COMMENT '收藏数',
    `comment_count` INT DEFAULT 0 COMMENT '评论数',
    `share_count` INT DEFAULT 0 COMMENT '分享数',
    `video_cover` VARCHAR(1024) DEFAULT NULL COMMENT '静态封面URL',
    `video_addr` VARCHAR(1024) DEFAULT NULL COMMENT '视频播放地址',
    `image_list` JSON DEFAULT NULL COMMENT '图集图片URL列表',
    `tags` JSON DEFAULT NULL COMMENT '话题标签列表',
    `raw_data` JSON DEFAULT NULL COMMENT '原始API响应',
    `upload_time` VARCHAR(32) DEFAULT NULL COMMENT '发布时间',
    `ip_location` VARCHAR(128) DEFAULT NULL COMMENT 'IP属地',
    `last_update_time` VARCHAR(64) DEFAULT NULL COMMENT '上次更新时的数值快照时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_note_id` (`note_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_upload_time` (`upload_time`),
    KEY `idx_note_id` (`note_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 作品数值快照表（用于追踪点赞/评论等数据变化）
CREATE TABLE IF NOT EXISTS `spider_tiktok_note_snapshot` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `crawl_task_id` VARCHAR(64) NOT NULL COMMENT '爬取任务ID',
    `crawl_time` DATETIME NOT NULL COMMENT '爬取时间',
    `note_id` VARCHAR(64) NOT NULL COMMENT '作品ID',
    `liked_count` INT DEFAULT 0 COMMENT '点赞数快照',
    `collected_count` INT DEFAULT 0 COMMENT '收藏数快照',
    `comment_count` INT DEFAULT 0 COMMENT '评论数快照',
    `share_count` INT DEFAULT 0 COMMENT '分享数快照',
    `detail_crawl_succeeded` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '详情爬取是否成功',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_crawl_task_id` (`crawl_task_id`),
    KEY `idx_note_id` (`note_id`),
    KEY `idx_crawl_time` (`crawl_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 异步爬取任务表
CREATE TABLE IF NOT EXISTS `spider_tiktok_crawl_job` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `job_id` VARCHAR(64) NOT NULL UNIQUE COMMENT '任务唯一ID',
    `job_type` VARCHAR(32) NOT NULL COMMENT 'search / account / mix',
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending / running / completed / failed',
    `parameters` JSON DEFAULT NULL COMMENT '任务参数',
    `error_message` TEXT DEFAULT NULL COMMENT '错误信息',
    `total_notes` INT DEFAULT 0 COMMENT '预期爬取的作品总数',
    `completed_notes` INT DEFAULT 0 COMMENT '已爬取的作品数',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    `started_at` DATETIME DEFAULT NULL COMMENT '开始执行时间',
    `completed_at` DATETIME DEFAULT NULL COMMENT '完成时间',
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_job_id` (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- API客户端注册表（用于Spider_XHS兼容的客户端认证）
CREATE TABLE IF NOT EXISTS `spider_tiktok_client` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `client_id` VARCHAR(64) NOT NULL UNIQUE COMMENT '客户端ID',
    `client_key` VARCHAR(255) NOT NULL COMMENT '客户端密钥（加密）',
    `permissions` JSON DEFAULT NULL COMMENT '权限列表',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
