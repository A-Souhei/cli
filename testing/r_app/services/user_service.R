# User service layer

# Source dependencies
source("models/user.R")

#' Create a new UserService
#'
#' @return List representing a UserService
#' @export
create_user_service <- function() {
  service <- list(
    users = list(),
    next_id = 1
  )

  class(service) <- "UserService"
  return(service)
}

#' Add a new user
#'
#' @param service UserService object
#' @param name User name
#' @param email User email
#' @return Updated service and created user
#' @export
add_user <- function(service, name, email) {
  user <- create_user(service$next_id, name, email)
  service$users[[length(service$users) + 1]] <- user
  service$next_id <- service$next_id + 1

  return(list(service = service, user = user))
}

#' Get user by ID
#'
#' @param service UserService object
#' @param user_id User ID
#' @return User object or NULL if not found
#' @export
get_user_by_id <- function(service, user_id) {
  for (user in service$users) {
    if (user$id == user_id) {
      return(user)
    }
  }
  return(NULL)
}

#' Get all users
#'
#' @param service UserService object
#' @return List of all users
#' @export
get_all_users <- function(service) {
  return(service$users)
}

#' Update user
#'
#' @param service UserService object
#' @param user_id User ID
#' @param name New name (optional)
#' @param email New email (optional)
#' @return Updated service and user
#' @export
update_user <- function(service, user_id, name = NULL, email = NULL) {
  for (i in seq_along(service$users)) {
    if (service$users[[i]]$id == user_id) {
      if (!is.null(name)) {
        service$users[[i]]$name <- name
      }
      if (!is.null(email)) {
        if (!validate_email(email)) {
          stop(paste("Invalid email address:", email))
        }
        service$users[[i]]$email <- email
      }
      return(list(service = service, user = service$users[[i]]))
    }
  }
  return(list(service = service, user = NULL))
}

#' Delete user
#'
#' @param service UserService object
#' @param user_id User ID
#' @return Updated service and success status
#' @export
delete_user <- function(service, user_id) {
  for (i in seq_along(service$users)) {
    if (service$users[[i]]$id == user_id) {
      service$users[[i]] <- NULL
      return(list(service = service, success = TRUE))
    }
  }
  return(list(service = service, success = FALSE))
}

#' Search users by name or email
#'
#' @param service UserService object
#' @param query Search query
#' @return List of matching users
#' @export
search_users <- function(service, query) {
  query <- tolower(query)
  results <- list()

  for (user in service$users) {
    if (grepl(query, tolower(user$name), fixed = TRUE) ||
        grepl(query, tolower(user$email), fixed = TRUE)) {
      results[[length(results) + 1]] <- user
    }
  }

  return(results)
}

#' Get users as data frame
#'
#' @param service UserService object
#' @return Data frame with all users
#' @export
get_users_df <- function(service) {
  if (length(service$users) == 0) {
    return(data.frame())
  }

  df_list <- lapply(service$users, user_to_df)
  do.call(rbind, df_list)
}
